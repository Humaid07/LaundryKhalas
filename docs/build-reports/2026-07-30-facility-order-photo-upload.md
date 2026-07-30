# Build Report — Facility Order Photo Upload (intake + pre-dispatch)

1. **Build title:** Facility order photos — intake + pre-dispatch proof upload.
2. **Date:** 2026-07-30.
3. **Task objective:** Let laundry partners attach garment/item photos to an order
   at two stages — **intake** (received at facility) and **pre-dispatch** (before
   handoff) — for proof, QC, dispute handling and damage tracking, with the upload
   workflow on the order detail page and a subtle status badge on order cards.

4. **What was built**
   - New `order_photos` table (metadata only; bytes in storage), migration 000032.
   - Backend repo + service (validation, local storage, audit) + 4 facility-scoped
     endpoints (list / upload / delete / stream content), registered in `main.py`.
   - Photo counts added to the facility orders **list** response for the card badge.
   - Frontend: api-client photo methods (multipart upload + Bearer blob fetch) and
     five `components/orders/` components; an **Order Photos** section on the order
     detail page and a photo badge on the order card.
   - 3 seeded development test orders (LK-TEST-FAC-001/002/003) + their intake photos.
   - `python-multipart` added (FastAPI file uploads).

5. **Why:** Proof/QC/dispute/damage evidence and internal ops visibility per the task
   brief; keeps the main upload UI on the detail page (card stays clean).

6. **Files created**
   - `supabase/migrations/20260730_000032_order_photos.sql`
   - `apps/whatsapp-agent/db/repositories/order_photos_repo.py`
   - `apps/whatsapp-agent/services/order_photos.py`
   - `apps/whatsapp-agent/api/facility_order_photos.py`
   - `apps/whatsapp-agent/tests/test_facility_order_photos.py`
   - `apps/whatsapp-agent/scripts/apply_order_photos.py`
   - `apps/whatsapp-agent/scripts/verify_order_photos.py`
   - `apps/whatsapp-agent/scripts/seed_facility_order_photos_test_data.py`
   - `apps/facility-dashboard/components/orders/OrderPhotosSection.tsx`
   - `apps/facility-dashboard/components/orders/OrderPhotoStageCard.tsx`
   - `apps/facility-dashboard/components/orders/OrderPhotoUploader.tsx`
   - `apps/facility-dashboard/components/orders/OrderPhotoGrid.tsx`
   - `apps/facility-dashboard/components/orders/OrderPhotoBadge.tsx`
   - `docs/architecture/facility-order-photos.md`
   - `docs/checklists/facility-order-photos-test-script.md`
   - this report.

7. **Files modified**
   - `apps/whatsapp-agent/main.py` (import + include the photos router)
   - `apps/whatsapp-agent/settings.py` (`FACILITY_ORDER_PHOTO_*` config + properties)
   - `apps/whatsapp-agent/db/repositories/facility_orders_repo.py` (photo counts on list)
   - `apps/whatsapp-agent/pyproject.toml` (`python-multipart`)
   - `apps/whatsapp-agent/.gitignore` (`storage/order-photos/`)
   - `apps/facility-dashboard/lib/api-client.ts` (types + photo methods + multipart/blob helpers)
   - `apps/facility-dashboard/app/(app)/orders/[orderId]/page.tsx` (Order Photos section)
   - `apps/facility-dashboard/components/orders/OrderCard.tsx` (photo badge)
   - `docs/00-Home.md` (this entry).

8. **API endpoints added** (all `/api/facility`, facility-scoped)
   - `GET /orders/{order_id}/photos?stage=` — list + per-stage counts.
   - `POST /orders/{order_id}/photos` — multipart (`stage`, `files[]`).
   - `DELETE /orders/{order_id}/photos/{photo_id}` — soft-delete (owner/manager).
   - `GET /orders/{order_id}/photos/{photo_id}/content` — stream bytes (Bearer-guarded).
   - `GET /orders` now also returns `intake_photo_count` / `pre_dispatch_photo_count`.

9. **Database changes:** new `order_photos` table + indexes + stage/provider CHECK
   constraints + RLS deny policy (migration 000032). No existing table altered.

10. **UI pages/components changed:** order detail page gains an **Order Photos**
    section (two stage cards, uploader modal, thumbnail grid); order cards gain a
    subtle **OrderPhotoBadge**.

11. **Agent behavior:** none (facility-facing feature; the WhatsApp agent is untouched).

12. **Integrations:** none live. Local dev file storage only.

13. **Mock-only / dev:** local storage (`FACILITY_ORDER_PHOTO_STORAGE=local`), gitignored
    folder; the 3 LK-TEST-FAC-00x orders + seeded intake photos are flagged
    `is_test_data=true` (`seed_source='facility_order_photo_seed'`).

14. **Live:** the endpoints run against the dev/test Supabase (migration applied +
    verified there); nothing points at production and no cloud storage secrets exist.

15. **Intentionally deferred:** cloud storage provider (Supabase Storage / R2) +
    signed URLs; future stages (`damage_report`/`issue_photo`/`quality_check`,
    schema-ready); internal ops read-only gallery; server-side thumbnailing.

16. **Tests run**
    - `pytest tests/test_facility_order_photos.py -q`
    - `pytest tests/test_facility_orders.py tests/test_facilities_management.py -q` (regression)
    - `npm run typecheck` · `npm run lint` · `npm run build` (facility-dashboard)
    - `scripts/verify_order_photos.py`
    - Live API round-trip (upload/list/content/delete/reject) + Playwright UI check.

17. **Test results**
    - Backend photo tests: **13 passed**. Facility regression: **44 passed**.
    - Frontend: typecheck **clean**, lint **clean** (1 pre-existing unrelated warning),
      build **exit 0** (21 pages).
    - `verify_order_photos.py`: **all checks passed** (table/columns/CHECKs/RLS + insert
      round-trip + stage-CHECK rejection).
    - Live: upload → 200 (generated file name, no PII); PDF → 415; content → 200
      `image/jpeg`; delete → 200 (count back to 0). Playwright (mobile viewport):
      Order Photos section + **2 thumbnails render**, list badges show, **no horizontal
      overflow, zero console errors**.

18. **Bugs/issues found & fixed during build**
    - `python-multipart` missing → FastAPI file uploads would fail; added to
      `pyproject.toml` and installed.
    - Seed script printed a `→` char that crashed on the Windows cp1252 console →
      switched to ASCII output.

19. **Known limitations**
    - Seeded thumbnails use a 1×1 placeholder JPEG (real photos come from real uploads).
    - No image compression/thumbnailing; bytes stored as uploaded (5MB cap).
    - Local storage is per-machine (not shared/persistent across environments).

20. **Security/privacy notes**
    - Facility scoping enforced app-side (`facility_id`) + RLS deny to public roles;
      another facility's order → 404.
    - Type allow-list **and** magic-byte check (renamed exe / SVG rejected); SVG blocked.
    - Size (5MB) + per-stage count (10) ceilings. Generated UUID file names (no PII, no
      path traversal). Content endpoint Bearer-guarded, `Cache-Control: private`.
    - Every upload/delete writes an `order_events` audit row with PII-safe metadata.

21. **Cost/LLM usage:** none (no LLM calls).

22. **Screens to demo:** `/orders` (card badges) → `/orders/LK-TEST-FAC-002` (Order
    Photos section with 2 intake thumbnails) → upload a photo to intake on
    LK-TEST-FAC-001 → see it appear + Timeline event.

23. **Commands to run:** see `docs/checklists/facility-order-photos-test-script.md`.

24. **How to verify manually:** follow the test-script checklist (setup → automated →
    manual UI → privacy → API smoke).

25. **Next recommended step:** wire a real cloud storage provider (R2/Supabase Storage)
    behind the existing `storage_provider` switch + signed URLs.

---

## Addendum (same day) — internal ops read-only view

Added the read-only ops/admin view of order photos (was listed as deferred above;
now built).

- **Backend** (`api/orders.py`, `require_ops` = admin + operations):
  - `GET /api/orders/{order_id}/photos` — photos + per-stage counts (any facility's
    order, via `orders_repo.get_read`).
  - `GET /api/orders/{order_id}/photos/{photo_id}/content` — stream bytes; the photo
    must belong to the order.
  - New `order_photos_repo.get_any` (non-facility-scoped, ops-only) +
    `services/order_photos.read_content_by_id` (with an `order_uuid` guard).
- **Frontend** (`apps/admin`): new `components/dashboard/orders/OrderPhotosPanel.tsx`
  (read-only gallery, blob-fetched thumbnails, empty state), wired into the live
  Orders section drawer (`OrdersSection.tsx`); `agentApi.getOrderPhotos` +
  `orderPhotoObjectUrl` + a blob helper in `lib/dashboard/whatsapp-agent-api.ts`.
- **Files:** created `apps/admin/components/dashboard/orders/OrderPhotosPanel.tsx`;
  modified `apps/whatsapp-agent/api/orders.py`, `services/order_photos.py`,
  `db/repositories/order_photos_repo.py`, `tests/test_facility_order_photos.py`,
  `apps/admin/lib/dashboard/whatsapp-agent-api.ts`,
  `apps/admin/components/dashboard/orders/OrdersSection.tsx`.
- **Read-only:** ops cannot upload or delete — those stay facility-side.
- **Tests/verify:** backend photo tests now **16 passed** (+3 ops); ruff clean; admin
  `tsc` clean + `next lint` clean on changed files. Live: ops-role login → `/orders`
  → open LK-TEST-FAC-002 → Order photos panel renders 2 intake thumbnails (Playwright:
  2 figures / 2 `<img>` / 0 skeleton; in-browser probe list=200 content=200
  `image/jpeg`; 0 console errors). Admin full `next build` skipped (a dev server was
  live on :3000 — Windows 500.html rename quirk; verified via tsc + lint + Playwright
  per repo guidance).
- **Dev note:** created a throwaway ops account `ops-photocheck@laundrykhalas.com`
  (dev/test Supabase) for the UI check; harmless, upserts by email.
