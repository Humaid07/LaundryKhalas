# Build Report — Facility Auto-Assignment + New-Order Notification

- **Date:** 2026-07-27
- **Task objective:** Close the gap left by the Facility Dashboard foundation: when a customer confirms a WhatsApp booking, automatically assign the order to a partner facility and notify that facility (mock-first). Previously `orders.facility_id` was only ever set by the seed script — real confirmed orders never reached a facility.

## What was built
A small, self-contained routing step wired into the **booking-confirmation** path:
1. **Facility selection** (`facilities_repo.select_for_location`) — a single DB-driven query that picks the best facility for the order's pickup location.
2. **Idempotent assignment** (`orders_repo.set_facility`) — attaches `facility_id` exactly once.
3. **Routing orchestration** (`services/facility_routing.py`) — ties selection + assignment together, writes a `facility_assigned` audit event, and **never raises** into the booking flow.
4. **Webhook wiring** — on the first-time confirm, the Evolution webhook assigns a facility and fires `facility_notifications.notify_new_order_assigned` (mock-first).

## Why
The Facility Dashboard foundation shipped with orders seeded to a facility but no live path from a real booking to a facility. Partners could only ever see demo data. This makes a freshly-confirmed customer order show up in the correct facility's dashboard and (mock-)notifies them — the first live data flow into the partner workspace.

## Files created
- `apps/whatsapp-agent/services/facility_routing.py`
- `apps/whatsapp-agent/tests/test_facility_routing.py` (8 tests)
- `docs/build-reports/2026-07-27-facility-auto-assign-and-notify.md` (this file)

## Files modified
- `apps/whatsapp-agent/db/repositories/facilities_repo.py` — added `select_for_location(area, city, emirate)` + `_ACTIVE_LOAD_STATUSES`.
- `apps/whatsapp-agent/db/repositories/orders_repo.py` — added `set_facility(order_uuid, facility_id)` (null-guarded, idempotent).
- `apps/whatsapp-agent/api/evolution_webhooks.py` — import `facility_orders_repo`, `facility_notifications`, `facility_routing`; in the `confirm_now` branch, on `created_now` assign facility + notify.

## API endpoints added/changed
None. This is a background step inside the existing WhatsApp confirmation flow — no new routes.

## Database tables/models added/changed
None (schema unchanged). Uses existing `orders.facility_id` (migration 000016), `facilities`, `order_events`, and `facility_notifications`. Writes a new `order_events` row with `event_type='facility_assigned'`, `actor_type='system'`.

## Agent behavior added/changed
On a customer's **first** booking confirmation, the system now:
1. Selects a facility by pickup location and current load.
2. Sets `orders.facility_id` (once).
3. Records a `facility_assigned` audit event.
4. Logs a `facility_notifications` row (mock by default; a live send only when a live facility channel is ready — none is wired yet).

### Selection ranking (best first)
1. **Location match:** area > city > emirate (case-insensitive).
2. **Operating status:** `open` preferred over `busy`. `closed`/`paused` and inactive facilities are excluded entirely.
3. **Spare capacity:** a facility whose active load is below `capacity_daily` is preferred.
4. **Least loaded**, then **oldest** facility (stable tie-break).

If **no** active facility can currently take work, the order is left **unassigned** for ops — nothing is force-routed and no data is invented.

## What is mock-only
- The facility notification defaults to `FACILITY_NOTIFICATIONS_MODE=mock` → a `facility_notifications` row is logged, nothing is sent externally.
- Facility payout/rates remain deferred (unchanged from the foundation).

## What is live
- The selection query runs against the live dev/test Supabase and was smoke-tested there.
- Assignment + audit event are real DB writes in dev/test.

## What is intentionally deferred
- **Capacity hard-limits / rejection:** capacity is a soft ranking signal, not a hard cap — an over-capacity facility can still be chosen if it's the only match. A true "facility full → route elsewhere / queue" policy is a follow-up.
- **Re-routing / rebalancing:** assignment is happen-once; reassigning a facility is an ops-only action (CLAUDE.md §6) and not automated here.
- **Non-WhatsApp order creation paths:** only the WhatsApp booking-confirm path is wired (it is the sole real order-creation path today).
- **Live facility notification channel:** the mock-first row is logged; an actual WhatsApp/other send to facility contacts is future work behind an approved provider.

## Tests run + results
- `tests/test_facility_routing.py` — **8 passed** (selection SQL shape, idempotent null-guard, assign skips when already assigned, assign selects+sets+audits, no-candidate → None, lost-race → None, never-raises).
- Facility + booking + evolution suites (`test_facility_*`, `test_booking_flow`, `test_multi_order`, `test_evolution_channel`) — **97 passed**.
- **Full backend suite — 608 passed** (was 600; +8 new), 178s.
- **Live Supabase smoke** of `select_for_location`:
  - `Dubai Marina/Dubai/Dubai` → `FAC-DXB-MARINA` (area match, active_load 9).
  - `Al Danah/Abu Dhabi/Abu Dhabi` → `FAC-AUH-CENTRAL` (area match — a busy facility is still chosen on a location match).
  - unknown location → fallback `FAC-DXB-MARINA` (open + under capacity, preferred over the busy AUH facility).

## Bugs/issues found (and fixed)
- The live smoke test surfaced `asyncpg.AmbiguousParameterError: could not determine data type of parameter $1` — Postgres couldn't infer the location params' type from `IS NOT NULL`. Fixed with explicit `::text` casts in the CASE. Unit tests (SQL-capture) could not have caught this; only the live run did.

## Known limitations
- Soft capacity only (see deferred).
- Fallback assignment can send an order to a geographically non-matching facility when no location match exists (acceptable with the current 2-facility dev set; ops can raise an issue / reassign).

## Security/privacy notes
- The facility notification preview carries **no** customer phone/email/full address — only order ref, service, and area/city (reuses `facility_orders_repo.to_facility_read` + `facility_notifications._new_order_preview`, both PII-safe per CLAUDE.md §7).
- The `facility_assigned` event stores only facility id/code + match basis, no customer PII.

## Cost/LLM usage notes
None — no LLM calls added. Pure DB + logging.

## Screens/pages to demo
- Confirm a booking from an allow-listed WhatsApp number → the order appears in that facility's dashboard (`apps/facility-dashboard` → Orders → "In" bucket) and a notification row appears in the facility's bell.

## Commands to run
- Backend: `cd apps/whatsapp-agent && ./.venv/Scripts/python.exe -m uvicorn main:app --host 0.0.0.0 --port 8100`
- Facility app: `cd apps/facility-dashboard && npx next dev -p 3010`
- Tests: `cd apps/whatsapp-agent && ./.venv/Scripts/python.exe -m pytest tests/test_facility_routing.py -q`

## How to verify manually
1. Start the backend (live dev/test Supabase) + facility app.
2. From an allow-listed number, complete + **confirm** a booking whose area is "Dubai Marina".
3. Confirm `orders.facility_id` is set to the Marina facility, an `order_events` row `facility_assigned` exists, and a `facility_notifications` row (`type='new_order_assigned'`, `status='mock_logged'`) was written.
4. The order shows in the Marina facility dashboard's "In" bucket.

## Next recommended step
Add a **capacity/attention signal** to the facility overview when a facility is at/over `capacity_daily`, and decide the over-capacity routing policy (queue vs. spill to next-best facility). Then trial live facility notifications behind an approved channel.
