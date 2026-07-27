# Facility Dashboard — Manual Test Script

## Prereqs
- Migrations 000016–000020 applied + `python -m scripts.seed_facility_data` run (dev/test Supabase).
- Backend: `cd apps/whatsapp-agent && ./.venv/Scripts/python.exe -m uvicorn main:app --host 0.0.0.0 --port 8100`
- App: `cd apps/facility-dashboard && npx next dev -p 3010`
- Facility login (when `REQUIRE_AUTH=true`): `owner@marina.lk.test` / `Facility#2026`. In dev (`REQUIRE_AUTH=false`) the app opens scoped to the Marina facility without login.

## Backend / API (verified)
- [x] `GET /api/facility/overview` → counts + operating status (200)
- [x] `GET /api/facility/orders?bucket=in|out|upcoming|attention|completed` → PII-safe orders (area/city only, no phone/email/address)
- [x] `GET /api/facility/me` → facility profile + role
- [x] `GET /api/facility/finance/summary` → revenue_total, payout_status=`pending_rate`, payout_amount=null
- [x] `GET /api/internal/facility-issues` → seeded issue visible to ops
- [x] `pytest tests/test_facility_*.py` → 39 passed; full suite 569 passed (6 unrelated fixture-race errors)

## Mobile app (390×844 viewport)
- [ ] Every route renders, **no horizontal overflow**, no runtime crash: `/`, `/orders` (5 buckets), `/orders/[id]`, `/finance` (+revenue/services/payouts), `/settings` (+6 subsections), `/issues` (+detail, +new)
- [ ] Bottom nav (Home/Orders/Finance/Settings) + header operating-status chip + notifications bell + Report Issue button
- [ ] Light + dark mode both legible

## Order lifecycle (facility actions)
- [ ] Open an "Orders In" order → Accept → Start Cleaning → Mark Ready → Confirm Handoff; each writes an `order_events` row and advances the status
- [ ] Forbidden: no Cancel/Refund/Change-price/Complete controls; backend rejects such actions (403)

## Issue → internal dashboard sync
- [ ] Raise an issue (floating Report Issue or order detail) → appears under `/issues` with status
- [ ] In `apps/admin` Operations → Facility Facing → Issues tab (with `NEXT_PUBLIC_USE_LIVE_WHATSAPP_INBOX=true`) → the issue shows
- [ ] Reply from the internal dashboard → the reply appears in the facility's issue thread
- [ ] Internal-only note (is_internal) is NOT visible to the facility

## Notifications
- [ ] `FACILITY_NOTIFICATIONS_MODE=mock` (default) → a new-order notification logs a `facility_notifications` row and shows in the notification center; nothing sends externally

## Privacy
- [ ] No customer phone/email/full address/payment anywhere in the app or API responses
- [ ] Facility B cannot read Facility A's orders/issues/finance (backend scoped by facility_id)

## Finance
- [ ] Service value + service-mix charts render from real orders; payout shows "pending — rates not configured" (no invented number)
