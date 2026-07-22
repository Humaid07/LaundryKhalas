# Build Report — WhatsApp Laundry-Pickup Booking State Machine

**Date:** 2026-07-22
**Author:** Engineering (Claude)
**Related:** [[2026-07-22-whatsapp-supabase-order-capture]] · [[2026-07-22-evolution-sender-allowlist]] · [[whatsapp-agent-architecture]]

## 1–3. Objective & root cause
Fix the hallucinated booking: "I need a laundry pickup" was replying "Got it —
Wash & Fold, Dubailand, today" and creating a draft order, though the customer
had selected nothing. **Root cause (two defects):** (a) the Evolution webhook
used a *stateless* extraction layer and created a draft as soon as `has_booking_
details()` saw **any one** field, and (b) the webhook **bypassed** the only
existing state machine (`order_flow.py`) by calling `handle_message(db=None)`, so
replies came from the mock/LLM template. Replaced with an explicit **persisted
state machine** where the DB is the source of truth and the LLM never decides a
transition, invents a value, or confirms a booking.

## 4. What was built
A deterministic booking FSM: `waiting_for_service → waiting_for_pickup_date →
waiting_for_pickup_slot → waiting_for_address → waiting_for_pickup_instructions
→ waiting_for_confirmation → booking_confirmed | booking_cancelled` (+
`waiting_for_instruction_text`, `waiting_for_change_field`). Services load from
the JSON catalogue (stable `service:<key>` ids); pickup slots load from a new
DB-backed availability system; instructions from config. Interactive WhatsApp
lists/buttons are sent via Evolution v2.3.7 with a numbered-text fallback.

## 5. Files created
- `apps/whatsapp-agent/services/booking_flow.py` — the pure FSM (states,
  interactive reply model, deterministic validators, numbered fallback).
- `apps/whatsapp-agent/db/repositories/slots_repo.py` — capacity/weekday/emirate/
  service-scoped slot availability.
- `apps/whatsapp-agent/config/pickup_instructions.json` — stable instruction options.
- `supabase/migrations/20260722_000005_whatsapp_booking_state.sql`.
- `apps/whatsapp-agent/tests/test_booking_flow.py` — the 12 required scenarios (+ extras).

## 6. Files modified
- `api/evolution_webhooks.py` — routes inbound through the FSM; **idempotency**
  (wa_message_id dedup); interactive send + fallback; confirm-once; removed the
  eager-draft/`_confirmation_reply` extraction path.
- `channels/evolution_whatsapp.py` — `send_list`/`send_buttons` (v2.3.7) + parse
  `listResponseMessage`/`buttonsResponseMessage`/`templateButtonReplyMessage`/
  `locationMessage` (exposes `selection_id`, `latitude`, `longitude`).
- `db/repositories/orders_repo.py` — `start_booking`, `apply_booking_updates`,
  `confirm_booking` (idempotent = single operational order), `cancel_booking`;
  `to_read` now surfaces booking fields.
- `db/repositories/messages_repo.py` — `wa_message_id` param + `wa_message_seen`.
- `rules.py` — `pickup_instructions()`. `agents/whatsapp_agent/prompts.py` —
  booking-safety guardrails. `schemas.py` — `pickup_instructions` + `booking_state`.
- `apps/admin/…/LiveWhatsAppOrders.tsx` (+ pickup time/instructions columns),
  `whatsapp-agent-api.ts` (DTO fields; base URL `:8100`→`:8101`).

## 7. Database changes (migration 000005, additive + idempotent)
- `orders` += `conversation_state, service_name_snapshot, pickup_date,
  pickup_slot_id, pickup_area, pickup_start_time, pickup_end_time, pickup_emirate,
  pickup_latitude, pickup_longitude, address_source, pickup_instruction_code,
  pickup_instruction_text, service_selected_at, confirmed_at`.
- `messages` += `wa_message_id` + partial unique index (idempotency).
- New `pickup_slots` table (+ RLS + updated_at trigger) seeded with 5 windows.
- **Also applied the previously-unapplied migration 000004** (`service_taxonomy`),
  which had left the live happy path broken (`orders.service_id` was missing).

## 8. Agent behaviour
- Booking intent only *detects intent* — no service/date/time/address/price is
  ever assumed. First reply: "Sure! Which laundry service would you like to book?"
  + the interactive list of all active services.
- Each step validates deterministically (past dates rejected; only DB slots
  offered; invalid/inactive service re-prompts the list; free-text service
  resolves only on a unique alias match). Escalations still interrupt and flag.

## 9–15. Mock/live, deferred, security
- Live: Evolution send/receive, Supabase persistence, DB slot availability.
- No price is invented (manual-quote services never auto-priced). Address is
  backend-only; phones masked in logs; no secrets logged. `.env` not committed.
- Deferred: reverse-geocoding a shared location into an area/emirate; per-service
  slot restrictions beyond the scoping columns; richer change-details revalidation.
- Removed the "Demo mode — I've created a mock booking…" text from the live path.

## 16–17. Tests & results
- `pytest` → **263 passed** (18 new booking tests + full regression), ruff clean,
  admin `tsc` clean for changed files.
- **Live Supabase integration** (in-process, no WhatsApp sent): full flow drives
  start→service→date→slot→address→instructions→confirm; asserts empty draft, each
  field persisted, area not hallucinated, and the operational order created
  exactly once (idempotent re-confirm). PASSED.
- **Live webhook** (running server, real Evolution): "I need a laundry pickup" →
  draft `waiting_for_service` with all fields null, service list sent via
  `sendList` (no fallback needed), `processed:1`. The 500 found during
  verification (a structlog `event=` kwarg clash) was fixed.

## 18–19. How to verify / acceptance
From an approved test number send "I need a laundry pickup" → you get the service
list, **not** a booking. Pick service → asked for date; today/tomorrow/other →
asked for a slot (from DB); address → instructions → summary → **Confirm booking**
creates the order once and it appears in the dashboard (Operations → Customer
Orders → Live WhatsApp orders) with service/date/time/address/instructions/status.

## 20. Next steps / limitations
- Interactive list/button rendering over WhatsApp depends on the recipient's app;
  the numbered-text fallback guarantees the flow still works.
- Consider migrating the SQLite chat-path `order_flow.py` onto the same FSM so
  both channels share one booking engine.
