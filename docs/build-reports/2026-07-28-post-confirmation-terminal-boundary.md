# Build Report — Post-Confirmation Terminal Boundary (WhatsApp Booking)

**Date:** 2026-07-28
**Area:** WhatsApp Operations Agent — Claude-orchestrated booking (`apps/whatsapp-agent`)

## 1. Objective
After an order is confirmed, the agent must send exactly ONE confirmation and
then stay silent until the customer sends a new explicit request. Stop the
spurious post-confirmation stream (discount explanation, "add more items", second
confirmation, apology, goodbye, repeated total).

## 2. Reproduced failure (from the screenshot)
Customer confirmed once → correct confirmation sent → then several more messages
(discount note, add-items invite, re-confirmation, apology, goodbye, repeated
total), some ~18 minutes later and several within a minute.

## 3. Root cause (traced through the real path)
The production path is Claude orchestration. `run_booking_turn` builds the state
block from `orders_repo.get_active_draft`. **Once the order is confirmed, the
draft is gone (`get_active_draft` → None), so the state block became
`{"workflow_state": "new", "missing_fields": ["service_items"]}`.** Every
subsequent turn therefore told Claude a NEW booking was starting, and — with the
confirmation still in history — Claude produced booking chatter (ask to book /
discount threshold / add items / re-confirm / closing). Any turn that reached
`_process_reply` after confirmation hit this:
- a re-driven **stale/recovered turn** (restart re-drive of a pre-confirmation
  turn → the ~18-minute gap, then a burst),
- a **duplicate "yes"**, or
- a later **customer ack** ("thanks").

There is **no** cron/timer/upsell/closing job — confirmed by a repo-wide search;
the chatter was entirely the model running a booking turn with a "new" state.
The confirm path itself already sends one reply and `confirm_booking` is
idempotent (`created_now=False` on a duplicate), so no second ORDER was created.

## 4. What was built
- **`services/post_confirmation.py` (new)** — the terminal boundary:
  - `is_confirmed_order(order)` — the persisted ORDER state is the authority: a
    status past `draft` (not cancelled/abandoned) or a `POST_ORDER` conversation
    state means the booking flow is over (no separate workflow_version column
    needed).
  - `classify_post_confirmation_turn(text)` → `NEW_ORDER | EDIT | QUERY | THANKS |
    NONE`. Only the first three are actionable; a bare "yes"/"confirm" echo,
    empty/interactive-only noise → `NONE`; gratitude → `THANKS`.
- **`api/evolution_webhooks.py` — terminal guard** at the top of the Claude
  branch: when there is **no active draft** and the latest order **is confirmed**:
  - non-actionable turn → **block the automated reply** (silence), mark the
    inbound `no_auto_reply`, log `post_confirmation_automation_blocked`
    (`reason=POST_CONFIRMATION_AUTOMATION_BLOCKED`). This stops the re-driven
    stale turns, duplicate "yes", and empty noise from ever running a booking
    turn.
  - gratitude → one brief `_THANK_YOU_TEXT` ("You're welcome! 😊"), logged
    `logical_turn_completed` (`final_response_type=THANK_YOU_RESPONSE`).
  - actionable (new order / edit / question) → proceed to the normal turn.
- **`booking_tools.confirmed_state_block()` (new)** + `run_booking_turn` change:
  when there's no draft but a confirmed order exists, the model is handed a
  terminal **ORDER_CONFIRMED** block (`missing_fields: []`, `booking_status:
  CONFIRMED`, `automation_state: IDLE`, `pending_confirmation: false`,
  `active_booking_complete: true`) instead of a "new" block — so even an explicit
  follow-up never re-books/re-confirms/upsells.
- **System prompt** hardened with an "After an order is confirmed — HARD STOP"
  block: one concise confirmation, then stop; no re-summary, re-confirm, discount
  volunteering, add-items upsell, or goodbye; wait for a new message; treat later
  changes as new targeted turns on the same order.
- The existing **outbound idempotency key** (`sha1(turn_id|state|body)` in
  `messages.metadata`, checked in `_deliver`) already suppresses a genuine
  duplicate send of the same confirmation reply for one turn.

## 5. Files
**Created:** `services/post_confirmation.py`, `tests/test_post_confirmation.py`,
this report.
**Modified:** `api/evolution_webhooks.py` (guard + `_THANK_YOU_TEXT` + import),
`agents/whatsapp_agent/booking_tools.py` (`confirmed_state_block`,
`run_booking_turn` state selection, system-prompt block, import).

## 6. API / DB / UI
No API routes, **no DB migration** (the confirmed ORDER state is the terminal
boundary; no new column). No UI changes.

## 7. Mock vs live
Deterministic backend logic (mock-first). No new live calls. The guard is
DB-backed (Supabase). Order confirmation remains idempotent
(`orders_repo.confirm_booking` → `created_now=False` on duplicate; the
`confirm_order` tool returns the existing order when the draft is already gone).

## 8. Logging added (safe ids only)
`post_confirmation_automation_blocked` (with `reason` + `turn_kind`),
`logical_turn_completed` (`final_response_type`). These join the existing
`booking_confirmed`, `anthropic_turn_delivered`, and `duplicate_outbound_prevented`.
No phone/address/secrets logged.

## 9. Tests run & results
`ruff check` — clean. `tests/test_post_confirmation.py` — **9 passed**:
- bare "yes"/"confirm" after confirmation → NONE (no message);
- gratitude (incl. "thanks Shinu") → THANKS;
- empty / bare interactive → NONE;
- explicit new order / edit / discount question → actionable;
- `is_confirmed_order` by status and by POST_ORDER state;
- `confirmed_state_block` is terminal + complete (AED 27, missing_fields empty);
- `run_booking_turn` with no draft + a confirmed order feeds an **ORDER_CONFIRMED**
  block (never `"workflow_state": "new"`).

Regression subset (booking tools, orchestration delivery, anthropic tool loop,
service persistence/resolution, outbound idempotency, turn service, message
aggregation) — **82 passed**, 0 regressions.

## 10. Manual verification
Live Evolution + LLM, approved test number: complete a booking, confirm once →
one confirmation, then silence. Send "yes"/"thanks"/an emoji → no booking chatter
(at most one "You're welcome"). Send "Why no discount?" or "change pickup time" →
handled as a new targeted turn against the same confirmed order. Restart the
backend after confirmation → no automatic replies resume (a re-driven stale turn
is blocked). Confirm twice / duplicate webhook → one order, one confirmation.

## 11. Known limitations / deferred
- A full **confirmed-order edit workflow** (mutating a confirmed order's items /
  pickup time with controlled re-confirmation) is not built; actionable
  post-confirmation edits currently run a normal Claude turn against the
  ORDER_CONFIRMED state (it will not re-book, and can `start_another_order`).
- Turn-level status columns (`turn_status`, `final_response_type`, explicit
  `workflow_version`) are not persisted; the terminal boundary is enforced from
  the authoritative confirmed ORDER state + the durable single-turn claim +
  outbound idempotency key, which achieve the same guarantees without a
  migration (avoided due to concurrent migration-number contention).
- The FSM (non-orchestration) legacy path already bounds post-order via
  `resolve_post_order_action`; the guard targets the default Claude path.

## 12. Next recommended step
Build the controlled confirmed-order edit flow (add-item / change-time with
re-confirmation) and, if a durable turn-status audit is wanted, add the
`conversation_turns` status columns in a coordinated migration.
