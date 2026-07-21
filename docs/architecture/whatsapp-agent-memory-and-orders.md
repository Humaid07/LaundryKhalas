# WhatsApp Agent — Conversation Memory & Order State

How the standalone WhatsApp agent remembers details across a conversation and
turns that conversation into a **persisted, queryable order** behind the scenes.

## The core idea

The agent does not just reply — for order intents it **reads and mutates a
real order row**. Chat is the interface; the order store is the state. A future
dashboard reads that state.

```
customer message ─▶ domain guard ─▶ escalation check ─▶ intent
                                                          │
                                    ┌─────────────────────┴───────────────┐
                                    ▼                                       ▼
                         order_flow.handle(db, conversation)      LLM(mock) reply path
                         (booking / track / cancel /              (greeting, pricing,
                          change / add — reads+writes              small talk, vague)
                          services/order_store.py)
```

`order_flow.handle` returns a deterministic, demo-honest reply for order turns,
or `None` to fall back to the normal reply path.

## Where things are stored

| State | Where | Survives restart? |
| --- | --- | --- |
| Conversation + messages | `conversations`, `messages` tables | Yes |
| Customer name / phone | `conversations` (+ copied onto the order) | Yes |
| Booking draft + active order (service, items, area, time, status, amount…) | `orders` table (`models.Order`) | Yes |
| Audit trail (intent, actions, order id, PII-masked) | `agent_logs` | Yes |

**Conversation "memory" of booking slots** (service / area / time) is derived
each turn from the message history via `tools.accumulate_slots` (a later
mention overrides an earlier one), and is **persisted** onto the draft order so
it is not lost. Item details are captured when the customer answers the
"share the item details" question and stored on the order.

There is **no separate in-memory store** — the database is the source of truth
(CLAUDE.md §5.9). The store interface in `services/order_store.py`
(`create_order`, `update_order`, `get_order`, `find_order_by_id`,
`list_active_orders`, `list_completed_orders`, `mark_completed`,
`add_order_note`, `add_order_items`, `request_cancellation`,
`request_pickup_change`, …) is storage-agnostic in shape, so moving SQLite →
Postgres needs no caller change.

## Pending-flow markers (state without extra tables)

A bare follow-up like `LK-AE-1024`, `2 suits`, or `yes` is routed back to the
right flow by looking at the **agent's previous message**. Each question leaves
a marker substring:

| Marker (in the agent's question) | Routes the next reply to |
| --- | --- |
| `help you check the status` | track order |
| `still be cancelled` | cancel — provide ID |
| `send a cancellation request` | cancel — confirmation |
| `new pickup time you prefer` | change pickup time |
| `items you would like to add` | add items |
| `share the item details` | booking — capture items |
| `please review and confirm` | booking — confirm |

See `tools.pending_order_action`, `tools.last_agent_asked`, and the marker
constants in `tools.py` / `order_flow.py`.

## Privacy

PII (phone/email) is masked before entering `agent_logs` (`services/privacy.py`).
The order stores the customer's own name/phone only. Facility/driver-facing
exposure of customer PII is **not** part of this module.

## Related

- [[mock-order-lifecycle]] — the status model and transitions.
- [[whatsapp-agent-rules]] — the config-driven rules / escalation / tone layer.
- [[2026-07-20-whatsapp-agent-stateful-orders]] — the build report.
