# Facility Order Photos (intake + pre-dispatch)

Garment/item **proof photos** a laundry partner attaches to an order at two
operational stages — **intake** (items received at the facility) and
**pre-dispatch** (before handoff/dispatch). Used for proof, quality control,
dispute handling, damage tracking and internal ops visibility.

Related: [[facility-dashboard]] · [[facility-privacy-firewall]] ·
[[facility-order-photos-test-script]] ·
build report `build-reports/2026-07-30-facility-order-photo-upload.md`.

## Stages

- `intake` — implemented.
- `pre_dispatch` — implemented.
- `damage_report`, `issue_photo`, `quality_check` — **reserved** in the DB `stage`
  CHECK constraint for the future, but the API accepts only the two above.

## Data model — `order_photos` (migration `20260730_000032`)

Only **metadata** lives in Postgres; the image **bytes** live in storage. Base64
image data is never stored in the DB.

| column | notes |
|---|---|
| `id` | uuid PK |
| `order_id` | uuid → `orders(id)` on delete cascade |
| `facility_id` | uuid → `facilities(id)` — scoping key on every read/write |
| `stage` | `intake` \| `pre_dispatch` (+ reserved future stages) |
| `storage_provider` | `local` \| `supabase` \| `r2` (dev default `local`) |
| `storage_key` | locates the bytes in storage (never returned to the client) |
| `public_url` | set only for a public cloud provider; null for local |
| `file_name` | generated `order-photo-<uuid>.<ext>` — never a client/PII name |
| `content_type` | `image/jpeg` \| `image/png` \| `image/webp` |
| `file_size` | bytes |
| `uploaded_by_user_id` / `uploaded_by_name` | uploader (id internal, label safe) |
| `metadata` | jsonb (stage only) |
| test-data markers | `is_test_data`, `is_demo`, `environment`, `seed_source`, … |
| `created_at` / `deleted_at` | soft-delete: evidence is never hard-deleted |

RLS: `revoke all … from anon, authenticated` + a restrictive deny policy
(`order_photos_no_public_access`), mirroring `facility_audit_log`. The backend
service role bypasses RLS and is the only reader/writer.

## Backend

- `db/repositories/order_photos_repo.py` — asyncpg CRUD; `to_read` is PII-safe
  (never returns `storage_key`/user id); `counts_for_orders` is one grouped query
  for the order-list badges (no N+1).
- `services/order_photos.py` — validation + storage + audit:
  - **Type allow-list** (`FACILITY_ORDER_PHOTO_ALLOWED_TYPES`, default JPG/PNG/WEBP)
    AND a **magic-byte** check — the declared content-type must match the real
    bytes, so a renamed executable or an SVG (text/`<`) is rejected. SVG is
    excluded (script-carrying vector).
  - **Per-image size** ceiling (`FACILITY_ORDER_PHOTO_MAX_MB`, default 5) and
    **per-stage count** ceiling (`FACILITY_ORDER_PHOTO_MAX_PER_STAGE`, default 10).
  - **Local storage** under `apps/whatsapp-agent/storage/order-photos/<order_uuid>/`
    (gitignored). Generated UUID file names → no path-traversal, no PII in names.
  - Every upload writes ONE `order_events` row
    (`intake_photos_uploaded` / `pre_dispatch_photos_uploaded`); a delete writes
    `order_photo_deleted`. Metadata is PII-safe (count, stage, uploader label).
- `api/facility_order_photos.py` — registered under the blanket
  `require_facility_scope` guard. Every route resolves the order through the
  **facility-scoped** lookup (`facility_orders_repo.get_row`); another facility's
  order → 404.

### Endpoints (all `/api/facility`, facility-scoped)

| method | path | purpose |
|---|---|---|
| GET | `/orders/{order_id}/photos?stage=` | list photos + per-stage counts |
| POST | `/orders/{order_id}/photos` | multipart upload (`stage`, `files[]`) |
| DELETE | `/orders/{order_id}/photos/{photo_id}` | soft-delete (owner/manager only) |
| GET | `/orders/{order_id}/photos/{photo_id}/content` | stream bytes (Bearer-guarded) |

The order **list** response also carries `intake_photo_count` /
`pre_dispatch_photo_count` per order (via `facility_orders_repo`) for the card badge.

## Frontend (`apps/facility-dashboard`)

- `lib/api-client.ts` — `orderPhotos`, `uploadOrderPhotos` (multipart, no forced
  JSON content-type), `deleteOrderPhoto`, `orderPhotoObjectUrl` (fetches the
  Bearer-guarded bytes as a revocable `blob:` URL — an `<img src>` can't send the
  token).
- `components/orders/`:
  - `OrderPhotosSection.tsx` — the "Order Photos" block on the order detail page
    (id `order-photos` for deep-scroll); owns the photos query.
  - `OrderPhotoStageCard.tsx` — one stage (count, upload button, grid/empty);
    highlights the stage matching the order's status.
  - `OrderPhotoUploader.tsx` — mobile-first upload sheet: multi-select, drag/drop,
    previews, remove-before-submit, client-side type/size/count validation.
  - `OrderPhotoGrid.tsx` — responsive thumbnail grid (2-col mobile / 3-col desktop);
    each thumb blob-fetches its bytes; inline delete for owner/manager.
  - `OrderPhotoBadge.tsx` — the subtle order-card indicator (guidance-only:
    "Intake photo needed" / "Dispatch photo needed" / "N photos").

## Privacy & security

- Facility users only ever see/upload photos for **their own** facility's orders
  (application-enforced `facility_id` scoping + RLS deny to public roles).
- No customer PII: file names are generated, metadata is stage-only, the content
  endpoint is Bearer-guarded (no open URL), and photos are garment/item only.
- The content bytes are streamed with `Cache-Control: private`.

## Storage modes

- `FACILITY_ORDER_PHOTO_STORAGE=local` (default) — dev/local folder, gitignored.
- `supabase` / `r2` — reserved; not wired (an upload in those modes returns 503
  rather than silently succeeding). **No cloud storage secrets are added by this
  feature.**

## Deferred

- Cloud storage provider (Supabase Storage / R2) + signed URLs.
- Future stages (`damage_report` / `issue_photo` / `quality_check`) — schema-ready.
- Internal (ops) dashboard read-only gallery — the data + `order_events` are in
  place for it; the internal UI is not built here.
- Image thumbnailing / server-side compression (bytes are stored as uploaded).
