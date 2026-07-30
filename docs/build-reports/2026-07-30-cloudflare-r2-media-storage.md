# Build Report — Cloudflare R2 media storage (extends order_photos)

**Date:** 2026-07-30

## 1. Build title
Add Cloudflare R2 (S3-compatible, private) media storage for LaundryKhalas — a
generic backend storage service + signed viewing — by **extending** the existing
`order_photos` feature in place (one unified, R2-backed order-media system), not a
parallel `order_media` table/API.

## 2. Task objective
Store actual media FILES in Cloudflare R2 while Supabase/Postgres stays the source
of truth (metadata only). Only FastAPI holds R2 credentials; dashboards upload/view
through FastAPI via short-lived signed URLs. Reconcile with the existing
`order_photos` work (owner decision: **extend in place, don't duplicate**): keep the
table name, routes, and UI components; add R2 + a signed `view-url` + generic media
columns; PII-safe object keys; never expose R2 keys to the frontend.

## 3. What was built
- **`services/media_storage.py`** — the single generic storage service: `upload_file`,
  `read_file`, `delete_file`, `create_signed_view_url`, `create_signed_upload_url`,
  `validate_file_type`, `validate_file_size`, `sha256_hex`. R2 via boto3 (S3 API) run
  in a threadpool (`asyncio.to_thread`); `local` disk fallback. **Fails fast (503)**
  when provider=r2 but credentials are missing (never a silent local fallback).
- **Config** in `settings.py`: `MEDIA_STORAGE_PROVIDER`, `CLOUDFLARE_R2_*`, `MEDIA_*`
  fields + parsed properties (`r2_is_configured`, `media_storage_provider_normalized`,
  size-in-bytes, type allow-list sets).
- **Migration 000034** — extends `order_photos` into the unified order-media record:
  adds `bucket, checksum_sha256, width, height, duration_seconds, source_channel,
  visibility_scope, status`; expands the `stage` CHECK to 8 stages.
- **`services/order_photos.py`** repointed to `media_storage` for all file I/O; new
  **PII-safe hierarchical object keys** `orders/{market}/{ref}/{stage}/{uuid}.{ext}`;
  stores `checksum_sha256` + provenance; added `signed_view_url()`.
- **Facility API**: new `GET …/photos/{id}/view-url` (signed, after the scope check);
  `…/photos/{id}/content` now proxies R2 too; upload passes market/order-ref for keys.
- **Facility dashboard**: `lib/api-client.ts` gains `orderPhotoViewUrl` + `provider`/
  `width`/`height` on the photo type. Existing `OrderPhoto*` components (section,
  uploader, grid, card badge) keep working unchanged (content proxy is R2-capable).
- **`.env.example`**: documented R2 block with **empty** credential placeholders.
- **boto3** added to `pyproject.toml` and installed into the backend venv.

## 4. Why it was built
Local disk was a dev stopgap for the facility photos feature; R2 is the durable,
private, S3-compatible store for real media, keeping Postgres lean (metadata only)
and credentials off the frontend.

## 5. Files created
- `apps/whatsapp-agent/services/media_storage.py`
- `supabase/migrations/20260730_000034_order_media_generic_columns.sql`
- `docs/architecture/media-storage-r2.md`
- `docs/checklists/r2-media-storage-test-script.md`
- `docs/build-reports/2026-07-30-cloudflare-r2-media-storage.md`

## 6. Files modified
- `apps/whatsapp-agent/settings.py` — MEDIA_/R2 config + properties.
- `apps/whatsapp-agent/services/order_photos.py` — R2 via media_storage; PII-safe
  keys; checksum; `signed_view_url`; removed the local-only `_save_local` + the
  "cloud not enabled" 503 gate.
- `apps/whatsapp-agent/db/repositories/order_photos_repo.py` — `create` accepts the
  new columns; `_SELECT_COLS` + `to_read` (exposes `provider`, `width`, `height`).
- `apps/whatsapp-agent/api/facility_order_photos.py` — `view-url` route; pass
  market/order-ref to upload.
- `apps/whatsapp-agent/pyproject.toml` — add `boto3`.
- `apps/whatsapp-agent/.env.example` — R2 section (empty secrets).
- `apps/whatsapp-agent/tests/test_facility_order_photos.py` — fixture repointed to
  the media_storage boundary; +15 R2/storage tests.
- `apps/facility-dashboard/lib/api-client.ts` — `orderPhotoViewUrl` + type fields.
- `docs/00-Home.md` — latest pointer.

## 7. Files deleted
None. (`_save_local` function removed from `order_photos.py`; no files deleted.)

## 8. API endpoints added/changed
- **Added** `GET /api/facility/orders/{order_id}/photos/{photo_id}/view-url` — signed
  short-lived view URL, only after the facility-scoped ownership check.
- **Changed** `GET …/photos/{photo_id}/content` — now serves R2-backed rows too
  (server proxies R2 bytes); contract unchanged.
- Upload/list/delete routes unchanged in shape.

## 9. Database tables/models added/changed
- `order_photos` extended (migration 000034): +`bucket, checksum_sha256, width,
  height, duration_seconds, source_channel, visibility_scope, status`; stage CHECK
  expanded to `intake, pre_dispatch, customer_reference, damage_report, issue_photo,
  quality_check, pickup_proof, delivery_proof`. **No new/parallel table.**

## 10. UI pages/components added/changed
- `apps/facility-dashboard/lib/api-client.ts` — `orderPhotoViewUrl`, `OrderPhotoViewUrl`
  type, `provider/width/height` on `FacilityOrderPhoto`. Existing `OrderPhoto*`
  components and the order-detail **Order Photos** section are unchanged (they keep
  working; the storage swap is transparent).

## 11. Agent behavior added/changed
None.

## 12. Integrations added/changed
- **Cloudflare R2** (S3-compatible) via boto3 — backend-only. Evolution/WhatsApp,
  Stripe, Anthropic unchanged.

## 13. What is mock-only
- Default `MEDIA_STORAGE_PROVIDER=local` (disk). No live R2 call happens until an
  operator sets `r2` + real credentials. Tests mock the S3 client — **no network**.

## 14. What is live
- Nothing external by default. R2 goes live only when configured with real creds
  (owner action); the code path is implemented and unit-tested against a mock client.

## 15. What is intentionally deferred
- Applying migration 000034 to the dev/test Supabase project (SQL written; needs
  manual apply, like prior migrations — **not** claimed as applied here).
- A real end-to-end R2 smoke test against a live bucket (needs creds; script in the
  checklist doc, section D).
- Image dimension extraction (`width`/`height` columns exist but stay null; no Pillow
  dep added — CLAUDE.md "don't overbuild").
- Direct-to-R2 signed **upload** URLs (`create_signed_upload_url` exists but the flow
  still uploads multipart through FastAPI).
- Switching the frontend thumbnails from the content proxy to signed URLs (kept the
  proxy for zero-churn; `orderPhotoViewUrl` is available for future use).

## 16. Tests run
- Backend: `./.venv/Scripts/python.exe -m pytest -q` (full suite) + the photo file.
- Backend lint: `ruff check` on all changed files.
- Frontend: `npm run typecheck`, `npm run lint`, `npm run build` (facility-dashboard).
- Security pre-flight: gitignore/tracking of `.env`, `.env.example` placeholders,
  grep for R2 secrets in both frontends.

## 17. Test results
- **Backend full suite: 1130 passed, 1 failed.** The one failure
  (`test_service_persistence.py::test_bespoke_wedding_dress_enters_bespoke_flow…`) is
  **pre-existing and unrelated** (bespoke booking flow; recorded in prior session
  memory as the same 1 pre-existing fail; this task touches none of that code).
- **`tests/test_facility_order_photos.py`: 30 passed** (15 existing + 15 new R2/storage).
- **ruff:** clean on all changed backend files.
- **Facility dashboard:** typecheck **clean**; lint **clean** apart from one
  **pre-existing, unrelated** warning in `app/(app)/orders/page.tsx` (untouched);
  build **succeeded** (all routes compiled).
- **Security:** `.env` gitignored + untracked; `.env.example` R2 vars are empty
  placeholders; **no** `CLOUDFLARE_R2_*` in `apps/admin`/`apps/facility-dashboard`
  (only deploy comments + a "Standby" status card); no `NEXT_PUBLIC_*` secret.

## 18. Bugs/issues found (and handled during the build)
- The existing test fixture monkeypatched `svc._save_local`, which the refactor
  removed. Repointed the fixture to the new **`media_storage.upload_file`** boundary
  (cleaner seam, still no disk/network in tests).
- Ensured provider selection can't silently degrade: r2-without-creds raises 503
  (asserted by `test_missing_r2_config_fails_safe_on_upload`).

## 19. Known limitations
- `order_photos` keeps its name though it is now the unified order-media record
  (owner decision — documented; avoids a broad rename). Column-name mapping
  (`storage_key`=object_key, `file_size`=file_size_bytes, `file_name`=generated,
  `stage`=media_stage) is documented in the migration + architecture doc.
- The client's **original filename is deliberately not stored** (PII); the spec's
  `original_file_name` column was intentionally omitted in favour of a generated
  name (CLAUDE.md §7). Noted as a conscious deviation.
- `width/height/duration_seconds` present but unpopulated (no media-probing dep yet).

## 20. Security/privacy notes
- R2 bucket private; credentials backend-only; never in any `NEXT_PUBLIC_*` var or
  frontend file. Signed URLs short-lived (300s) and minted only after the scope
  check. Facility isolation enforced (cross-facility → 404). Type allow-list +
  magic-byte check reject SVG/PDF/EXE/unknown. `checksum_sha256` stored; deletes are
  soft (evidence retained). Every upload/delete writes a PII-safe `order_events` row.
  Object keys carry no PII.

## 21. Cost/LLM usage notes
- No LLM usage. R2 storage/egress cost applies only once `r2` is enabled with real
  credentials; signed-URL viewing serves bytes directly from R2 (offloads FastAPI).

## 22. Screens/pages to demo
- Facility dashboard → an order → **Order Photos**: upload intake + pre-dispatch
  images; thumbnails render; card shows "Intake/Dispatch photo needed / N photos".
- (With R2 configured) show a row's `storage_provider='r2'` + object in the bucket at
  `orders/{market}/{ref}/{stage}/…`, and a signed `view-url` loading the image.

## 23. Commands to run
```
# Backend
cd apps/whatsapp-agent
./.venv/Scripts/python.exe -m pytest -q
./.venv/Scripts/python.exe -m ruff check services api db settings.py tests

# Frontend
cd apps/facility-dashboard
npm run typecheck && npm run lint && npm run build
```

## 24. How to verify manually
1. Security: `git check-ignore apps/whatsapp-agent/.env`; confirm `.env.example` R2
   vars are blank; grep both frontends for `CLOUDFLARE_R2` → none.
2. Default (local): upload a facility order photo; it stores on disk and renders.
3. Enable R2 (see `docs/checklists/r2-media-storage-test-script.md` §D) and run the
   live smoke test: upload → row `storage_provider='r2'` + object in bucket → signed
   `view-url` loads → PDF/SVG rejected → oversized rejected → cross-facility 404 →
   soft-delete keeps bytes + writes an event.

## 25. Next recommended step
Provision a private R2 bucket + token, set the secrets in the deployed `.env`, apply
migration 000034, and run the §D live smoke test. Then (optional) switch the
thumbnail grid to signed `view-url` to offload byte-proxying, and add image
dimension extraction to populate `width/height`.
