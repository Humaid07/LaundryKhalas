# Mock Order Lifecycle

The demo order state model used by the standalone WhatsApp agent
(`services/order_store.py`). Everything here is **mock** (`Order.is_demo =
true`) — no live order, driver, payment, or facility system is involved.

## Statuses

```
draft ──▶ active ──▶ pickup_scheduled ──▶ picked_up ──▶ in_cleaning
   │                                                        │
   │                                                        ▼
   │                                              ready_for_delivery
   │                                                        │
   │                                                        ▼
   │                                               out_for_delivery
   │                                                        │
   ▼                                                        ▼
cancelled / cancellation_requested                     completed
pickup_change_requested / support_required
```

| Status | Meaning | In "active" list? |
| --- | --- | --- |
| `draft` | Booking being collected in chat, not confirmed | No |
| `active` | Confirmed mock booking | Yes |
| `pickup_scheduled` | Pickup window set | Yes |
| `picked_up` | Collected | Yes |
| `in_cleaning` | At facility | Yes |
| `ready_for_delivery` | Cleaned, awaiting dispatch | Yes |
| `out_for_delivery` | On the way | Yes |
| `completed` | Done (`completed_at` set) | No — in "completed" |
| `cancelled` | Cancelled | No |
| `cancellation_requested` | Customer asked to cancel; team must confirm | Yes |
| `pickup_change_requested` | Customer asked to move pickup; team must confirm | Yes |
| `support_required` | Needs human | Yes |

"Active" = **not** `completed`/`cancelled` and **not** a bare `draft`. Requests
(`cancellation_requested`, `pickup_change_requested`) stay visible as active
because the team still has to action them.

## Rules

- A **new booking starts as `draft`** and is persisted from the moment a
  service is chosen.
- Once **service + items + area + time** are collected and the customer
  **confirms**, the draft flips to **`active`** and gets a `LK-AE-####` id
  (new bookings start at 2031; demo seeds are 1024–1027).
- **Cancel never auto-cancels.** The agent asks to confirm, then records
  `cancellation_requested`. A `completed` order cannot be cancelled from chat.
- **Change pickup time** records `pickup_change_requested` + the requested time
  in `change_request`; it never confirms the new time automatically.
- **Track** reads the stored status. Unknown IDs are refused, never invented.
- **Mark completed** sets `completed`, stamps `completed_at`, and moves the
  order out of active into completed.

## Seeded demo orders

| Order ID | Customer | Service | Status | Amount |
| --- | --- | --- | --- | --- |
| `LK-AE-1024` | Amaan | Wash & Fold + Dry Cleaning | `pickup_scheduled` (Today 6–8 PM, Dubai Marina) | AED 145 |
| `LK-AE-1025` | Sarah | Duvet Cleaning | `in_cleaning` (Abu Dhabi) | AED 90 |
| `LK-AE-1026` | Jumeirah Hotel | Business Laundry | `ready_for_delivery` (Dubai) | AED 2800 |
| `LK-AE-1027` | Test User | Ironing / Pressing | `completed` (Sharjah) | AED 60 |

Seeded idempotently on startup (`order_store.seed_demo_orders`). Reset per test
by the `_reset_orders` fixture.

## Metrics (`GET /api/orders/metrics`)

`active_orders`, `completed_orders`, `cancellation_requests`,
`pickup_change_requests`, `support_required`, `total_orders`,
`orders_by_status`.

## Related

- [[whatsapp-agent-memory-and-orders]]
- [[2026-07-20-whatsapp-agent-stateful-orders]]
