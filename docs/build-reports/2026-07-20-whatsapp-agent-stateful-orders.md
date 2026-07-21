# Build Report — WhatsApp Agent: Humanized Typing + Stateful Mock Orders

**Date:** 2026-07-20
**Module:** `apps/whatsapp-agent` (FastAPI, :8100) + `apps/whatsapp-chat` (Next.js, :3100)
**Mode:** Mock-only. No live WhatsApp, payments, LLM, driver, or facility systems.

## 1. Task objective

Make the standalone WhatsApp Operations Agent feel more **humanized**,
**stateful**, and **demo-realistic**: a typing indicator before replies,
conversation memory that persists customer/booking details, and — most
importantly — **the conversation must update a real, queryable order state
behind the scenes** so a future dashboard has live data to read.

## 2. What was built (summary)

- **Order state model + store** (`services/order_store.py`, `models.Order`):
  a persisted, queryable order row with the full lifecycle
  `draft → active → pickup_scheduled → … → completed / cancelled` plus
  `cancellation_requested` / `pickup_change_requested` / `support_required`.
- **Stateful order flows** (`agents/whatsapp_agent/order_flow.py`): booking,
  track, cancel, change-pickup-time and add-items now **read and mutate the
  order store**. Booking builds a draft order slot-by-slot and, on
  confirmation, flips it to an **active** order that appears in the dashboard
  active list. Track returns the real stored status; unknown IDs are refused,
  never invented.
- **Dummy demo orders** `LK-AE-1024..1027`, seeded idempotently at startup.
- **Order/dashboard API** (`api/orders.py`): active/completed/all/detail,
  mark-completed, status-update, and ops metrics.
- **Humanized typing indicator** (frontend): optimistic user bubble + a
  WhatsApp-style animated typing bubble held for a configurable 2–3s.
- **Config**: `AGENT_MIN_TYPING_DELAY_MS` / `AGENT_MAX_TYPING_DELAY_MS`,
  surfaced via `/api/settings/status`.

## 3. Why

Per founder direction: *"don't just make the chat reply — make the
conversation update an order state behind the scenes. This is what will make
the dashboard useful later."* The agent now produces **state**, not just text.

## 4. Files created

- `apps/whatsapp-agent/services/order_store.py` — order store (status model,
  seeding, CRUD, lookups, mutations, metrics, serialization).
- `apps/whatsapp-agent/agents/whatsapp_agent/order_flow.py` — deterministic,
  demo-honest stateful order flows.
- `apps/whatsapp-agent/api/orders.py` — order/dashboard REST API.
- `apps/whatsapp-agent/tests/test_orders.py` — 11 new endpoint + flow tests.
- `apps/whatsapp-chat/components/TypingIndicator.tsx` — typing bubble.
- Docs (this report + architecture/checklist/presentation notes).

## 5. Files modified

- `apps/whatsapp-agent/models.py` — added `Order` model.
- `apps/whatsapp-agent/settings.py` — typing-delay settings.
- `apps/whatsapp-agent/schemas.py` — `OrderRead`/`OrderMetrics`/`OrderStatusUpdate`,
  typing delays on `SettingsStatus`, `order_id`/`order_status` on `TestChatResponse`.
- `apps/whatsapp-agent/main.py` — include orders router; seed demo orders on startup.
- `apps/whatsapp-agent/api/settings_route.py` — expose typing delays.
- `apps/whatsapp-agent/api/chat.py` — pass `db`+`conversation` to the agent;
  surface order state on the response and in the audit log.
- `apps/whatsapp-agent/api/webhooks.py` — same `db`+`conversation` wiring (parity).
- `apps/whatsapp-agent/agents/whatsapp_agent/agent.py` — delegate order/booking
  turns to `order_flow`; `AgentReply` carries `order_id`/`order_status`.
- `apps/whatsapp-agent/agents/whatsapp_agent/actions.py` — `CONFIRM_ACTIONS`.
- `apps/whatsapp-agent/agents/whatsapp_agent/tools.py` — full-format order-ID
  regex (`LK-AE-1024`), pending-flow markers + `last_agent_asked`.
- `apps/whatsapp-agent/tests/conftest.py` — per-test order reset fixture;
  Windows-safe DB teardown.
- `apps/whatsapp-agent/tests/test_quick_actions.py`, `test_agent_rules.py` —
  updated for the new items step + real order lookups.
- `apps/whatsapp-agent/.env.example` — typing-delay vars.
- `apps/whatsapp-chat/app/chat/page.tsx` — optimistic bubble + typing delay.
- `apps/whatsapp-chat/app/globals.css` — typing-dot animation.
- `apps/whatsapp-chat/lib/types.ts` — typing delays + order fields.

## 6. API endpoints added

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/orders/active` | Orders in flight (dashboard active list) |
| GET | `/api/orders/completed` | Completed orders |
| GET | `/api/orders` (`?status=`) | All orders, optional status filter |
| GET | `/api/orders/metrics` | Ops metrics (counts by status, etc.) |
| GET | `/api/orders/{order_id}` | Single order (404 if unknown) |
| POST | `/api/orders/{order_id}/complete` | Mark completed |
| POST | `/api/orders/{order_id}/status` | Set status (validated) |

`TestChatResponse` now also returns `order_id` / `order_status` whenever a
turn created or touched an order.

## 7. Database models added/changed

- New `orders` table (`models.Order`). SQLite (dev) / Postgres-ready. All rows
  `is_demo = true`. Created by `Base.metadata.create_all` on startup — **no
  destructive migration**; existing `conversations`/`messages`/`agent_logs`
  tables are untouched.

## 8. Agent behavior added/changed

- **Booking** now collects **service → item details → area → time → review →
  confirm**, persisting a **draft order** each step and activating it on
  confirm. (Previously service → area → time with no item step and no order.)
- **Track** reads the stored status of a known order; refuses unknown IDs.
- **Cancel** asks for explicit confirmation, then records a
  `cancellation_requested` — never auto-cancels; refuses on completed orders.
- **Change pickup time** records a `pickup_change_requested` + `change_request`.
- **Add items** appends to the conversation's order.
- Escalation, domain guard, PII masking (from the prior rules layer) unchanged.

## 9. What is mock-only / live / deferred

- **Mock-only:** everything here. Orders are demo rows; no live tracking,
  cancellation, payment, driver, or facility. Every operational reply is
  demo-tagged.
- **Live:** nothing new is live.
- **Deferred:** dashboard UI wiring to these endpoints (endpoints are ready;
  the admin app already reads `:8100` for the WhatsApp console), classifier,
  live WhatsApp/Stripe/LLM, real order backend.

## 10. Tests run + results

- Backend: `pytest` → **129 passed** (was 95; +34). Ran with the project venv
  Python 3.12. Previously-flaky Windows DB teardown now handled cleanly.
- Live ASGI smoke: startup seeding, track (real status), metrics, complete,
  settings — all verified.
- Frontend: `npm run typecheck` and `npm run lint` → clean.

## 11. Known limitations / honesty notes

- **Item capture is greedy:** the message answering "share the item details"
  is stored verbatim as items. In the guided chip flow this is clean; free-text
  edge cases can capture extra words. Acceptable for demo.
- **Order source channel** for chat-console bookings is `local` (webhook
  bookings are `whatsapp`).
- **In-memory delay is frontend-side**; the backend never blocks.
- **Typing bubble** was verified via typecheck/lint + code review, not an
  automated browser screenshot this session (both dev servers were left as-is).
- A **concurrent session** refactored this module to config-driven rules while
  this work was in progress; this build integrates with that architecture.

## 12. Security / privacy

- No secrets added. PII masking in the audit log is preserved. Orders store
  customer name/phone only where the customer provided them in-conversation;
  facility-facing exposure is out of scope here.

## 13. Commands to run / verify

```bash
# Backend
cd apps/whatsapp-agent
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m uvicorn main:app --port 8100
# Frontend
cd apps/whatsapp-chat && npm run dev   # :3100
```

Manual verification: see
`docs/checklists/whatsapp-agent-stateful-order-test-script.md`.

## 14. Next recommended step

Wire the admin dashboard's Operations views to `/api/orders/*` (active,
completed, metrics) so booked/tracked/cancelled orders from chat show up
live. Then the classifier agent (still deferred).
