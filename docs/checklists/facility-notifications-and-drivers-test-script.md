# Test Script — Facility Notifications & Drivers

Manual verification for the two additions: (1) facility mobile notifications on
order/driver/issue events, (2) the Drivers section. Backend needs
`DATABASE_MODE=supabase` with migrations through `000023` applied + `seed_facility_data.py`
run. Notifications default to **mock** (nothing is sent externally).

## Setup
1. Apply migrations up to `20260727_000023_facility_drivers.sql` (asyncpg / Supabase SQL editor — no generic runner).
2. `cd apps/whatsapp-agent && python -m scripts.seed_facility_data` (needs `ALLOW_TEST_SEED=true`).
3. Env: `FACILITY_NOTIFICATIONS_MODE=mock`, `FACILITY_NOTIFICATIONS_LIVE_READY=false`.
4. Start backend on :8100 and facility-dashboard on :3010. Log in as the seeded owner (`owner@marina.lk.test` / `Facility#2026`).

## A. Notifications
- [ ] **New order assigned** — confirm a WhatsApp booking that auto-assigns to Marina → a `new_order_assigned` row appears in the header notification center (unread badge increments).
- [ ] **Status update** — from Orders, run a facility action (e.g. Start cleaning) → an `order_status_updated` notification appears; preview shows the order ref + "In cleaning" + SLA, and **no** customer phone/address.
- [ ] **Idempotency** — repeat the same status transition → no duplicate notification (dedupe_key).
- [ ] **Driver assigned** — assign a driver to an order (below) → a `driver_assigned` notification appears.
- [ ] **Internal issue reply** — from the internal dashboard, post a public reply on a facility issue → an `internal_issue_reply` notification appears on the facility side; internal note text is NOT in the preview.
- [ ] **Live blocked** — set `FACILITY_NOTIFICATIONS_MODE=whatsapp` while `LIVE_READY=false` → notifications still log as `mock_logged`, nothing sent.
- [ ] **Read/unread** — tap a notification → marked read, unread count drops.
- [ ] **Settings → Notifications** — add/edit a contact, toggle subscribed types (incl. the new `order_status_updated`, `driver_assigned`, `internal_issue_reply`), deactivate a contact.

## B. Drivers
- [ ] **Nav** — Drivers appears in the desktop sidebar (Home, Orders, Drivers, Finance, Issues, Settings) and in the mobile bottom nav (Home, Orders, Drivers, Finance, More).
- [ ] **List + tiles** — `/drivers` shows Free / On Job / Issues tiles and the seeded drivers; one driver reads **On Job** (seeded assignment), others **Free**.
- [ ] **Tabs** — All / Free / On Job / Pickup / Delivery / Issues filter correctly.
- [ ] **Card** — shows name, masked phone, status badge, current order ref + service, task, expected completion, area. No customer PII.
- [ ] **Detail** — `/drivers/{id}` shows header, current assignment, assignment history, issues panel, and (owner/manager) action buttons.
- [ ] **Assign** — assign an order to a free driver → driver flips to On Job, free count drops, order timeline gets a `driver_assigned` event, order detail shows the driver.
- [ ] **Double-book blocked** — assigning a busy driver returns a 422 error toast.
- [ ] **Complete/cancel** — completing the task frees the driver.
- [ ] **Permissions** — log in as `facility_staff` → management actions are hidden AND a direct API call returns 403.

## C. Isolation & privacy
- [ ] A driver/notification from Facility A is never visible to Facility B (facility-scoped queries).
- [ ] No notification or driver payload contains customer full phone / address / payment / internal notes.

## D. Mobile
- [ ] At 375px width there is no horizontal overflow on Drivers list, detail, or the notification sheet. Cards (not tables) on mobile; large tap targets.

## E. Automated
- [ ] `cd apps/whatsapp-agent && .venv/Scripts/python -m pytest tests/test_facility_drivers.py tests/test_facility_notifications.py -q` → all pass.
- [ ] `cd apps/facility-dashboard && npx tsc --noEmit` → clean.
