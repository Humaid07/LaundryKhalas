# Build Report — Facility auto-assign on the Claude (natural-language) confirm path

**Date:** 2026-07-28

## 1. Task objective
During a live WhatsApp manual test, confirmed orders were reaching the internal
dashboard but **not** the facility dashboard. Root cause: the natural-language
(Anthropic/Claude) `confirm_order` tool confirmed the order but never ran the
first-confirm side effects — facility auto-assign + notify, campaign attribution,
CRM recompute — which lived only in the deterministic FSM confirm branch. Since
`anthropic_booking_orchestration=true` is the DEFAULT path, in practice **no**
live-booked order auto-reached a facility. Objective: wire the Claude path to the
same side effects so both confirm paths behave identically.

## 2. What was built
- A shared, path-agnostic helper `services/order_confirmation.py::apply_post_confirmation_effects(order_row, customer_id)`
  that runs the four first-confirm effects, each idempotent + best-effort (never
  raises into the customer's confirmation reply):
  1. facility auto-assign by pickup location + load (`facility_routing`),
  2. mock-notify the assigned facility (`facility_notifications`, PII-safe),
  3. last-touch campaign attribution (`campaigns_repo`),
  4. CRM lifecycle/segment recompute (`crm_repo`).
- Both confirm paths now call this single helper on `created_now` (first confirm):
  - deterministic FSM: `api/evolution_webhooks.py` (block replaced by the helper),
  - Claude tool: `agents/whatsapp_agent/booking_tools.py` `confirm_order` handler.

## 3. Why
One source of truth for confirm side effects → the natural-language path (the
default) no longer silently skips facility assignment, and future confirm-effect
changes only need editing in one place.

## 4. Files
**Created:** `apps/whatsapp-agent/services/order_confirmation.py`
**Modified:**
- `apps/whatsapp-agent/api/evolution_webhooks.py` (call helper; dropped 4 now-unused imports)
- `apps/whatsapp-agent/agents/whatsapp_agent/booking_tools.py` (call helper on `created_now`)
- `apps/whatsapp-agent/tests/test_booking_tools.py` (autouse hermetic spy + regression test)

## 5. API / DB / UI
No API, schema, or UI changes. Behaviour-only fix. (Facility assignment writes
the existing `facility_assigned` order event; nothing new added.)

## 6. Agent behavior changed
Claude-orchestrated bookings now auto-assign a facility + notify it + attribute
campaigns + recompute CRM on first confirm — identical to the FSM path.

## 7. Mock / live / deferred
- Facility notifications remain **mock** (`FACILITY_NOTIFICATIONS_MODE=mock` → log only).
- Assignment, attribution, CRM are real DB writes (dev/test Supabase).
- No new live integrations.

## 8. Tests
- `test_booking_tools.py` + `test_orchestration_delivery.py` + `test_facility_routing.py`
  + `test_facility_notifications.py`: **33 passed**.
- New regression `test_claude_confirm_triggers_post_confirmation_effects`: asserts
  the Claude `confirm_order` path invokes the helper exactly once (first confirm),
  with the confirmed row + customer id, and NOT on the idempotent repeat.
- `ruff check` on all changed files: clean.
- **Live end-to-end** against real Supabase (real executor + real repos, LLM/WhatsApp
  transports excluded): confirming an order via the Claude executor produced
  `facility_assigned` (match_basis=area), set `facility_id`, and fired `crm_recomputed`.
  Test rows cleaned up.

## 9. Bugs found / fixed en route
- **Migration drift (separate, also fixed 2026-07-28):** `conversation_turns` was
  never applied to the dev Supabase → every inbound webhook 500'd ("agent cold").
  Applied migrations `000013` (+`000012`). `000011`/`000009`
  (`catalogue_version_items`) still missing but off the booking path. See
  `docs/build-reports` memory note.

## 10. Known limitations
- Fallback assignment: when a pickup area/city has no matching active facility,
  the router falls back to the least-loaded active facility (by design). Al Nahda
  had no exact facility, so earlier test orders matched Dubai Marina by fallback.
- Rate cards / real facility payout still mock (unchanged).

## 11. Security / privacy
Facility notification payload is PII-safe (`to_facility_read` — area/city only,
no customer phone/email). No new PII surface. No secrets touched.

## 12. How to verify manually
Book + confirm a pickup over WhatsApp (natural language). The confirmed order now
appears in BOTH the internal dashboard (Operations → Customer Orders) and the
facility dashboard (assigned facility + notification), with a `facility_assigned`
event on the order timeline.

## 13. Next recommended step
Backfill/apply the remaining drifted migrations to the dev Supabase
(`000009` pricing-management → then `000011`) so the published-pricing path is
consistent; consider a small migration-state check on startup.
