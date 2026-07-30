# Test script — Facility Order Photos

Manual + automated verification for the intake / pre-dispatch photo feature.
Related: [[facility-order-photos]] · build report
`build-reports/2026-07-30-facility-order-photo-upload.md`.

## Prerequisites

- Backend on :8100 with `DATABASE_MODE=supabase` (dev/test project), from the venv:
  `cd apps/whatsapp-agent && ./.venv/Scripts/python.exe -m uvicorn main:app --host 0.0.0.0 --port 8100`
- Facility dashboard on :3010: `cd apps/facility-dashboard && npm run dev`
- Migration applied + test data seeded (see below).

## One-time setup

```bash
cd apps/whatsapp-agent
./.venv/Scripts/python.exe scripts/apply_order_photos.py        # migration 000032
./.venv/Scripts/python.exe scripts/verify_order_photos.py       # expect "All checks passed."
PYTHONIOENCODING=utf-8 ./.venv/Scripts/python.exe -m scripts.seed_facility_order_photos_test_data
```

Seeds **LK-TEST-FAC-001/002/003** (scoped to the dev facility, `is_test_data=true`):

| order | status | area | intake | pre_dispatch |
|---|---|---|---|---|
| LK-TEST-FAC-001 | picked up | Dubai Marina | 0 | 0 |
| LK-TEST-FAC-002 | in cleaning | JLT | 2 | 0 |
| LK-TEST-FAC-003 | ready for delivery | Al Barsha | 1 | 0 |

## Automated tests

```bash
cd apps/whatsapp-agent
./.venv/Scripts/python.exe -m pytest tests/test_facility_order_photos.py -q   # 13 passed

cd apps/facility-dashboard
npm run typecheck    # clean
npm run lint         # clean (1 pre-existing warning in orders/page.tsx, unrelated)
npm run build        # exit 0 (stop the dev server first — Windows 500.html rename quirk)
```

Backend tests cover: (1) intake upload OK, (2) pre_dispatch upload OK,
(3) cannot upload for another facility's order → 404, (4) invalid type → 415,
(5) oversize → 413, (6) creates `order_photos` row, (7) creates order event,
(8) list scoped to caller's facility, (9) soft-delete + manage-only,
(10) no customer PII in metadata/file name (+ SVG rejected, content-type spoof
rejected, per-stage cap → 409, validation error → HTTP status mapping).

## Manual UI checks

### Order detail (`/orders/LK-TEST-FAC-002`)
- [ ] An **Order Photos** section renders with two cards: **Intake Photos** and **Pre-dispatch Photos**.
- [ ] Intake shows count **2** and two thumbnails (with uploaded time + "Facility Seed").
- [ ] Pre-dispatch shows count **0** and an empty state + **Upload pre-dispatch photos** button.
- [ ] The stage matching the order's status is subtly highlighted (sky ring).
- [ ] **Timeline** shows an "Intake Photos Uploaded" event.

### Upload flow
- [ ] Click **Upload intake photos** → a modal/sheet opens.
- [ ] Select multiple images → previews appear; each can be removed before submit.
- [ ] Submit → loading state → thumbnails appear in the grid; count increments.
- [ ] On mobile, the upload buttons are large; thumbnails are a 2-column grid; **no horizontal scroll**.
- [ ] Camera/gallery works on a mobile device (input accepts images).

### Validation (clean errors, no crash)
- [ ] A non-image file (PDF) is rejected with a clear message.
- [ ] An over-5MB image is rejected.
- [ ] More than 10 per stage is blocked.

### Delete (owner/manager)
- [ ] A thumbnail shows a delete control; removing it drops the count.
- [ ] A non-manager role does not get delete (and the API returns 403).

### Order list (`/orders`)
- [ ] LK-TEST-FAC-001 (picked up, 0 intake) shows an **"Intake photo needed"** badge.
- [ ] LK-TEST-FAC-002 shows a **"2 photos"** badge.
- [ ] Badges are subtle and don't clutter the card.

## Privacy checks
- [ ] Photo file names are `order-photo-<uuid>.<ext>` (no customer name/phone).
- [ ] The content endpoint requires the Bearer token (open URL → 401/404).
- [ ] Another facility's order id returns 404 (no data leak).

## API smoke (dev, REQUIRE_AUTH=false)

```bash
curl "http://localhost:8100/api/facility/orders/LK-TEST-FAC-002/photos"        # counts {intake:2}
curl -X POST "http://localhost:8100/api/facility/orders/LK-TEST-FAC-001/photos" \
     -F "stage=intake" -F "files=@photo.jpg;type=image/jpeg"                   # 200
curl -X POST "http://localhost:8100/api/facility/orders/LK-TEST-FAC-001/photos" \
     -F "stage=intake" -F "files=@doc.pdf;type=application/pdf"                # 415
```
