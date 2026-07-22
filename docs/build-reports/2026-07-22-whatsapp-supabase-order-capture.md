# Build Report — WhatsApp → Supabase order capture + live dashboard wiring

**Date:** 2026-07-22

## 1. Task objective
Turn every approved Evolution WhatsApp test chat into properly-structured Supabase
data — not just raw messages. Extract and persist customer, conversation, message,
**order**, **order-event**, and **flag/ticket** details as the customer books over
WhatsApp, maintain conversation memory across turns, and surface the live data on
the dashboard (Dashboard → FastAPI → Supabase only) behind a safe flag.

## 2. What was built
An extraction/order-state layer after inbound parsing, wired into the Evolution
webhook, plus Supabase repositories to create/update a per-conversation **draft
order** that accumulates details across messages and is promoted to
`pickup_scheduled`/`active` only on customer confirmation. Escalations raise a
flag **and** a ticket and never auto-resolve. Two live dashboard panels read the
data through FastAPI behind `NEXT_PUBLIC_USE_LIVE_WHATSAPP_INBOX`.

## 3. Why
Prior state only stored the raw inbound message + a draft reply. The business
needs the derived customer/order data (the thing ops and reporting consume). This
is the WhatsApp Operations Agent's core happy-path booking capability.

## 4. Files created
- `apps/whatsapp-agent/services/order_extraction.py` — `extract_customer_order_details(text, context)` + `accumulate_from_messages(...)`; name/city/area/address/service/items(qty)/pickup+delivery slot/payment/confirmation.
- `apps/whatsapp-agent/db/repositories/order_events_repo.py` — order-event audit writes.
- `apps/whatsapp-agent/db/repositories/tickets_repo.py` — idempotent ticket create/update.
- `apps/whatsapp-agent/api/tickets.py` — `GET /api/tickets`.
- `apps/whatsapp-agent/tests/test_order_extraction.py` — 13 extraction unit tests.
- `supabase/migrations/20260722_000003_whatsapp_order_capture.sql` — additive `customers.address`, `orders.pickup_address`.
- `apps/admin/components/dashboard/operations/live/useLiveAgentData.ts` — live-flag + fetch hook.
- `apps/admin/components/dashboard/operations/live/LiveWhatsAppOrders.tsx`
- `apps/admin/components/dashboard/operations/live/LiveWhatsAppConversations.tsx`

## 5. Files modified
- `api/evolution_webhooks.py` — added extraction → customer backfill → draft order + events → escalation flag **+ ticket** → gated auto-reply (with deterministic confirmation reply). Sender allow-list gate preserved.
- `db/repositories/orders_repo.py` — `create_or_update_draft_from_conversation`, `next_test_order_id` (`LC-TEST-####`), `get_open_for_conversation`, per-item amount estimate, `to_read(..., include_address=)` (privacy).
- `db/repositories/customers_repo.py` — `update_customer_details(...)`.
- `db/repositories/conversations_repo.py` — `link_order(...)`.
- `db/repositories/messages_repo.py` — `add_message(..., metadata=)`.
- `main.py` — register tickets router.
- `apps/admin/app/(dashboard)/operations/customer-orders/page.tsx` + `customer-facing/page.tsx` — mount live panels.
- `apps/admin/.env.example` — `NEXT_PUBLIC_USE_LIVE_WHATSAPP_INBOX=true`, agent URL → :8101.
- `apps/whatsapp-agent/.env` (gitignored) — corrected `EVOLUTION_ALLOWED_TEST_NUMBERS` to the approved test number.

## 6. API endpoints
Added `GET /api/tickets`. `GET /api/orders/{id}` now returns the full `pickup_address`
(secure detail only). `/api/orders`, `/api/orders/active|completed` mask the address.
No breaking changes to existing shapes.

## 7. Database
Additive columns only (`customers.address`, `orders.pickup_address`) — applied and
verified on the dev/test Supabase. WhatsApp-captured rows carry test markers
(`is_test_data=true`, `test_scenario_id=whatsapp_live_capture`, `created_by_seed=false`).

## 8. UI
Live panels (flag-gated): **Live WhatsApp orders** on `/operations/customer-orders`
(`/api/orders`); **Live WhatsApp conversations** + **open flags** on
`/operations/customer-facing` (`/api/conversations`, `/api/flags`). Loading / empty /
error / refresh states on each. Off by default → existing demo surfaces untouched.

## 9. Agent behavior
Draft order accumulates across turns and links to the conversation
(`linked_order_id`); confirmation promotes it and sends a deterministic confirmation
reply. Escalations → flag + ticket + `human_needed`, never auto-resolved. Auto-reply
still gated by allow-list + decision layer + `EVOLUTION_AUTO_REPLY`.

## 10–15. Mock / live / deferred
- **Live:** Evolution inbound + outbound, Supabase persistence, dashboard reads.
- **Mock:** LLM (reply text is mock-generated; confirmation replies are deterministic).
- **Deferred:** approval-queue writes for outbound, richer dashboard order-detail drawer, order-event UI timeline, `preferred_language` used only when Arabic detected.

## 16–18. Tests & results
- `pytest`: **208 passed** (195 prior + 13 new extraction tests).
- `ruff`: clean on all changed backend files.
- admin `tsc --noEmit`: **0 errors**; `eslint`: clean.
- **Live Supabase integration check** (throwaway rows, auto-cleaned): full Amaan
  booking flow → `LC-TEST-####` order, `pickup_scheduled`, 7 event types, customer
  backfill, address masked in list / exposed in detail, amount 30 AED (2×15),
  idempotent (no duplicate). All endpoints (`/health/db`, `/api/conversations`,
  `/api/orders`, `/api/orders/active`, `/api/flags`, `/api/tickets`) return 200.

## 19. Known limitations
- Reply text is mock-LLM; only the confirmation message is deterministic.
- Item/name/address extraction is heuristic (deterministic regex), not an LLM/NER —
  unusual phrasings may be missed (no invented data on a miss).
- A pre-existing `LC-TEST-1001` may sit in the dev DB from earlier manual testing.

## 20. Security / privacy
- Full phone only in `customers.phone_e164`; APIs return `masked_phone`.
- Full pickup address stored backend-only; **never** in list APIs / broad tables —
  only the secure single-order detail. No phone/address/keys logged.
- Dashboard talks to FastAPI only; never Supabase directly. `.env` not committed.

## 21. Cost / LLM
No live LLM calls (mock provider). No new external cost.

## 22. Demo
`/operations/customer-orders` (Live WhatsApp orders) and `/operations/customer-facing`
(Live conversations + flags) with `NEXT_PUBLIC_USE_LIVE_WHATSAPP_INBOX=true`.

## 23. Commands
- Backend: `cd apps/whatsapp-agent; .venv\Scripts\python -m uvicorn main:app --reload --port 8101`
- Tests: `.venv\Scripts\python -m pytest -q`
- Admin: `cd apps/admin; npm run dev` (set `NEXT_PUBLIC_USE_LIVE_WHATSAPP_INBOX=true`, `NEXT_PUBLIC_WHATSAPP_AGENT_API_URL=http://localhost:8101`)

## 24. How to verify manually
From **+971502485658** message the agent (Test 1–7 in the request). Confirm a
conversation + order appear via `/api/conversations`, `/api/orders`, and the live
dashboard panels; a "refund/dirty clothes" message raises a flag + ticket and no refund.

## 25. Next recommended step
Point the Evolution webhook to `http://host.docker.internal:8101/webhooks/evolution`,
then run the live Test 1–7 from the approved number; optionally add an order-detail
drawer + event timeline to the dashboard.
