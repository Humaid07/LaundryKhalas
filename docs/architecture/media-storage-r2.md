# Media Storage — Cloudflare R2 (S3-compatible)

**Status:** implemented (backend + facility dashboard), mock-first default `local`.
**Last updated:** 2026-07-30

## 1. Decision

- **Supabase/Postgres stays the source of truth.** It stores only media
  **metadata** (the `order_photos` table — the unified order-media record). Base64
  media is **never** stored in the database.
- **Cloudflare R2 stores the actual files** in a **private**, S3-compatible bucket.
- **Only the FastAPI backend holds R2 credentials.** The admin and facility
  dashboards upload and view media **exclusively through FastAPI** — they never see
  an R2 key and never talk to R2 directly.
- **Evolution API** remains the WhatsApp media channel (unchanged by this work).

### Reconcile, don't duplicate

There was already a working facility **order photos** feature (migration 000032:
`order_photos` table, `services/order_photos.py`, `api/facility_order_photos.py`,
facility-dashboard `OrderPhoto*` components) using **local** disk storage. Rather
than build a parallel `order_media` table + `/media` routes + `OrderMedia*`
components, we **extended `order_photos` in place** into the unified, R2-backed
order-media record. This keeps the existing routes, UI, and table name stable and
avoids churn. `order_photos` is now the **legacy/stable name for the unified order
media system**; it supports R2-backed photos today and future media types without
breaking existing UI/routes.

## 2. Components

| Layer | File | Role |
|---|---|---|
| Config | `apps/whatsapp-agent/settings.py` | `MEDIA_STORAGE_PROVIDER`, `CLOUDFLARE_R2_*`, `MEDIA_*` fields + parsed props (`r2_is_configured`, `media_storage_provider_normalized`, size/type sets). |
| Storage service | `apps/whatsapp-agent/services/media_storage.py` | The ONE place that talks to object storage. `upload_file`, `read_file`, `delete_file`, `create_signed_view_url`, `create_signed_upload_url`, `validate_file_type`, `validate_file_size`, `sha256_hex`. R2 via boto3 (S3 API) in a threadpool; `local` fallback. |
| Metadata table | `supabase/migrations/…000032_order_photos.sql` (+ `…000034_order_media_generic_columns.sql`) | `order_photos` — the unified order-media record. |
| Repo | `apps/whatsapp-agent/db/repositories/order_photos_repo.py` | Reads/writes the metadata rows; PII-safe `to_read`. |
| Feature service | `apps/whatsapp-agent/services/order_photos.py` | Validation + orchestration; builds PII-safe object keys; calls `media_storage`; writes audit events. |
| Facility API | `apps/whatsapp-agent/api/facility_order_photos.py` | `GET/POST/DELETE …/photos`, `GET …/photos/{id}/content` (Bearer byte proxy), `GET …/photos/{id}/view-url` (signed). |
| Ops read-only | `apps/whatsapp-agent/api/orders.py` | `GET /api/orders/{id}/photos` + `/content` (internal, non-facility). |
| Facility UI | `apps/facility-dashboard/components/orders/OrderPhoto*` + `lib/api-client.ts` | Order Photos section, uploader, thumbnail grid, card badges; `orderPhotoViewUrl`. |

## 3. Provider selection

```
MEDIA_STORAGE_PROVIDER=local   # dev/test fallback — files on local disk (gitignored)
MEDIA_STORAGE_PROVIDER=r2      # Cloudflare R2 — CLOUDFLARE_R2_* required
```

- Default is **`local`** (mock-first, CLAUDE.md §5). No cloud creds needed for dev.
- When `r2` is selected but any `CLOUDFLARE_R2_*` credential is missing, the storage
  layer **fails fast with 503** — it never silently falls back to local (which would
  lose an upload). `settings.r2_is_configured` is the guard.

## 4. Object keys are PII-safe

```
orders/{market_code}/{order_ref}/{stage}/{uuid}.{ext}
e.g. orders/AE/LK-AE-1024/intake/9f2c…a1.jpg
```

- `market_code` = order `market` (e.g. `AE`); `order_ref` = the business order code
  (e.g. `LK-AE-1024`). Both are slugged to `[A-Z0-9-]`.
- The key contains **no** customer name, phone, full address, facility name, or
  driver name. The stored `file_name` is a **generated** `order-photo-<uuid>.<ext>`
  — the client's original filename is deliberately **not** persisted (it can carry
  PII; CLAUDE.md §7).

## 5. Viewing (private bucket)

R2 objects are private (`public_url` is null). Two read paths, both after the
facility-scoped ownership check:

1. **Signed view URL** — `GET …/photos/{id}/view-url` returns a short-lived
   (`MEDIA_SIGNED_URL_EXPIRES_SECONDS`, default 300s) presigned GET URL straight to
   R2. Returned **only** after the permission check. `url` is null for `local`.
2. **Bearer content proxy** — `GET …/photos/{id}/content` streams the bytes through
   FastAPI (works for both `local` and `r2`). The facility-dashboard thumbnail grid
   uses this today (unchanged), so the switch to R2 needs no UI change.

## 6. Security posture (CLAUDE.md §7/§9)

- R2 bucket is **private**; credentials are backend-only and never reach a
  `NEXT_PUBLIC_*` var. Verified: no `CLOUDFLARE_R2_*` in `apps/admin` /
  `apps/facility-dashboard` (only deploy-adapter comments + a "Cloudflare R2 —
  Standby" integration status card).
- Signed URLs are **short-lived** and minted only after the ownership check.
- A facility can never read/write another facility's media (every route resolves
  the order via the **facility-scoped** `facility_orders_repo.get_row`; a mismatch
  is a 404).
- **Type allow-list + magic-byte check**: only `image/jpeg|png|webp`; the declared
  type must match the file's real bytes → **SVG, PDF, EXE, and unknown types are
  rejected** (415). Per-file size ceiling (413).
- `checksum_sha256` is stored for integrity/audit; **soft-delete** keeps the bytes
  as evidence (the row is marked deleted; `media_storage.delete_file` — a hard
  purge — is intentionally **not** called on the delete path).
- Every upload/delete writes an **`order_events`** audit row with PII-safe metadata.

## 7. `order_photos` schema (post-000034)

Existing (000032): `id, order_id, facility_id, stage, storage_provider,
storage_key, public_url, file_name, content_type, file_size, uploaded_by_user_id,
uploaded_by_name, metadata, is_test_data, is_demo, environment, seed_*, created_at,
deleted_at`.

Added (000034): `bucket, checksum_sha256, width, height, duration_seconds,
source_channel (default 'facility_dashboard'), visibility_scope (default
'facility'), status (default 'active')`. Stage CHECK expanded to `intake,
pre_dispatch, customer_reference, damage_report, issue_photo, quality_check,
pickup_proof, delivery_proof` (the facility API still only accepts
`intake`/`pre_dispatch`).

**Column-name mapping** (existing name = generic concept, not duplicated):
`storage_key` = object_key · `file_size` = file_size_bytes · `file_name` =
generated safe name (original filename intentionally not stored) · `stage` =
media_stage.

`visibility_scope` makes the record **internal-visibility-ready** (item 8 of the
spec): internal/admin reads can later filter `visibility_scope in ('facility',
'internal')` without a schema change.

## 8. Environment variables

Backend-only (`apps/whatsapp-agent/.env`, gitignored; placeholders in
`.env.example`):

```
MEDIA_STORAGE_PROVIDER=local            # or r2
CLOUDFLARE_R2_ACCOUNT_ID=               # secret
CLOUDFLARE_R2_BUCKET=                    # secret
CLOUDFLARE_R2_ENDPOINT=                  # secret
CLOUDFLARE_R2_ACCESS_KEY_ID=            # secret
CLOUDFLARE_R2_SECRET_ACCESS_KEY=        # secret
CLOUDFLARE_R2_REGION=auto
MEDIA_SIGNED_URL_EXPIRES_SECONDS=300
MEDIA_UPLOAD_SIGNED_URL_EXPIRES_SECONDS=300
MEDIA_MAX_IMAGE_MB=10
MEDIA_MAX_VIDEO_MB=100
MEDIA_ALLOWED_IMAGE_TYPES=image/jpeg,image/png,image/webp
MEDIA_ALLOWED_VIDEO_TYPES=video/mp4,video/quicktime
```

## 9. Enabling R2 (checklist)

1. Create a **private** R2 bucket; create an R2 API token (Object Read & Write).
2. Put the five `CLOUDFLARE_R2_*` secrets + `MEDIA_STORAGE_PROVIDER=r2` in the
   backend's local/deployed `.env` (never commit).
3. Apply migration `20260730_000034` to the dev/test Supabase project.
4. Restart the backend; upload a photo from the facility dashboard; confirm the row
   has `storage_provider='r2'` and the object appears in the bucket under
   `orders/{market}/{ref}/{stage}/…`.
5. Confirm the thumbnail renders (content proxy) and `view-url` returns a signed URL.

See also: [[r2-media-storage-test-script]], the build report
`build-reports/2026-07-30-cloudflare-r2-media-storage.md`, and
[[project_2026-07-30_facility-order-photos]] (the feature this extends).
