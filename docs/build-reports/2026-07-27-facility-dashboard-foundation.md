# Build Report — Facility (Laundry Partner) Dashboard

- **Date:** 2026-07-27
- **Objective:** Build a separate, mobile-first dashboard for laundry partner facilities (distinct from the internal admin dashboard), scoped per facility, privacy-safe, with orders, finance, settings, issues (synced to the internal dashboard), and mock-first notifications.

## What was built
A new standalone app `apps/facility-dashboard` (Next.js, mobile-first, port **3010**) talking only to the existing FastAPI backend (`apps/whatsapp-agent`, **:8100**) → Supabase. Plus the backend facility API, DB schema, per-facility auth scoping, mock-first notifications, and facility-issue surfacing inside the internal admin dashboard.

## Why
LaundryKhalas partners need a simple operational workspace (mostly mobile) to manage incoming/outgoing orders, see facility revenue, manage facility settings, and raise issues to the internal team — without seeing customer PII or other facilities' data.

## Database (migrations applied to the dev/test Supabase project)
`supabase/migrations/20260727_000016_facilities.sql` … `000020_facility_settings.sql` (renumbered to 000016–000020 to avoid a number collision with a concurrent session's 000011–000013):
- `facilities` (+ `orders.facility_id` FK, indexed) — `payout_rate` is a **nullable placeholder** (facility rates fed later).
- `users` widened: facility roles (`facility_owner|facility_manager|facility_staff|facility_driver`) + `facility_id` scope column.
- `facility_issues` + `facility_issue_messages` (threaded).
- `facility_notifications` + `facility_notification_contacts`.
- `facility_settings`, `facility_timings`, `facility_blackout_dates`, `facility_team_members`, `facility_price_change_requests`.
- All RLS-enabled (no anon policies; backend service-role bypasses), standard test-data markers, `set_updated_at` triggers.
- **Seed** (`scripts/seed_facility_data.py`): 2 facilities (`FAC-DXB-MARINA`, `FAC-AUH-CENTRAL`), all demo orders linked to Marina, a **facility-owner login `owner@marina.lk.test` / `Facility#2026`**, default settings/timings/team/contact, and a demo issue.

## Backend (apps/whatsapp-agent)
- **Auth/scope:** `services/auth.py` facility roles; `facility_id` JWT claim (`api/auth.py`); `api/deps.py::require_facility_scope` (resolves + enforces the caller's facility_id — dev scopes to the seeded facility; prod locks a facility user to their own). `users_repo` carries `facility_id`.
- **Repos:** `facilities_repo`, `facility_orders_repo` (bucketed, facility-scoped, PII-safe serializer), `facility_finance_repo` (revenue/service-mix aggregates), `facility_issues_repo`, `facility_issue_messages_repo`, `facility_notifications_repo`, `facility_settings_repo`.
- **Services:** `facility_orders.py` (allowed status transitions: accept / mark_received / start_cleaning / move_to_qc / mark_ready / confirm_handoff; **forbids** cancel/refund/price-change/complete/reassign). `facility_notifications.py` (mock-first, env-gated, idempotent, never-raises — mirrors `services/notifications.py`).
- **Settings:** `facility_notifications_mode` (default `mock`), `facility_notifications_ready`, `validate_facility_notifications_config()` (called in lifespan). CORS adds `:3010`.

## API endpoints added
- Facility (guard `require_facility_scope`, every query scoped to the caller's facility): `GET /api/facility/me`, `/overview`, `/orders` (`?bucket=in|out|upcoming|attention|completed&range=&from=&to=`), `/orders/{id}`, `PATCH /orders/{id}/status`, `POST /orders/{id}/notes`, `POST /orders/{id}/issues`, `/finance/{summary,revenue,services,payouts}`, `/settings/{profile,operations,timings,prices,team,notifications}` (+ `prices/change-request`), `/issues` (+ `/{id}`, `/messages`, `/resolve`), `/notifications` (+ read / unread-count).
- Internal (guard `require_ops`): `GET /api/internal/facility-issues`, `/{id}`, `/{id}/messages`, `POST /{id}/reply`, `PATCH /{id}/status`.

## Frontend — new app `apps/facility-dashboard`
Mobile-first shell (bottom nav Home/Orders/Finance/Settings + header w/ operating-status chip + notifications bell; desktop sidebar; floating Report Issue). Routes: `/` Overview, `/orders` (5 buckets + date filters, card view), `/orders/[orderId]` (detail + timeline + actions), `/finance` (+ revenue/services/payouts, Recharts), `/settings` (+ price/operations/teams/timings/notifications/profile), `/issues` (+ `[issueId]` thread, `new`), `/login`. Reuses the admin design system (tokens, `ui/*` + `minimal/*` components, charts) copied in; data via a `facilityApi` client (Bearer JWT, 401→login).

## Internal dashboard change (apps/admin)
Facility issues now surface in Operations → Facility Facing (the existing "Issues" tab wired to live `/api/internal/facility-issues`) with a full detail/thread page (facility vs internal bubbles, reply + internal-note toggle, status controls). Facility roles added to the role types (no admin-app access).

## Mock-only / live status
- **Mock-first:** facility notifications default to `mock` (log a `facility_notifications` row, no external send). Facility payout/rates are **not implemented** (deferred) — Finance shows customer order value ("Completed Service Value") and payout as `pending_rate`.
- **Live:** the facility API runs against the live dev/test Supabase; the admin backend on :8100.

## Tests run + results
- Facility backend tests: **39 passed** (`tests/test_facility_orders.py`, `test_facility_finance.py`, `test_facility_issues.py`, `test_facility_notifications.py`).
- Full backend suite + frontend tsc/build: see the checklist; run at integration time.
- **Live API smoke (verified):** `/api/facility/overview`, `/orders?bucket=in`, `/me`, `/finance/summary` (revenue AED 47.25, payout pending), `/internal/facility-issues` all return correct, PII-safe data against Supabase.

## Privacy / security notes
Facility serializers return order id, service/items, **area/city only**, operational instructions, SLA, status, order value, driver label, and a customer **first-name label** — never phone/email/full address/payment/private notes. Every facility query is filtered by the authed `facility_id` (backend-enforced; RLS-bypassing service role, so isolation is in application SQL + tested). Notifications never include full address/phone.

## Known limitations / deferred
- Facility payout **rates deferred** (placeholder column + price-change-request table exist).
- Order→facility assignment is seeded; automatic routing on new bookings + a live "new order assigned" notification trigger in the booking flow are follow-ups.
- QC and "received at facility" reuse nearest existing order statuses (`in_cleaning`/`picked_up`) since the orders table has no dedicated facility statuses.
- A concurrent session is mid-adding `conversation_turns`/pricing features; a harmless startup warning (`relation "conversation_turns" does not exist`) comes from that unapplied migration, not this work.

## Commands
- Backend: `cd apps/whatsapp-agent && ./.venv/Scripts/python.exe -m uvicorn main:app --host 0.0.0.0 --port 8100`
- Facility app: `cd apps/facility-dashboard && npx next dev -p 3010` (env `NEXT_PUBLIC_FACILITY_API_URL=http://localhost:8100`)
- Seed: `cd apps/whatsapp-agent && ./.venv/Scripts/python.exe -m scripts.seed_facility_data`

## Next recommended step
Wire a `facility_notifications.notify_new_order_assigned(...)` call into the booking-confirmation path + auto-assign a facility on new orders, then trial live facility notifications behind `FACILITY_NOTIFICATIONS_MODE=whatsapp`.
