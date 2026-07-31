# Pre-Confirmation Review Gate — Design Spec

**Date:** 2026-07-31
**Status:** Awaiting review
**Area:** WhatsApp Operations Agent — booking confirmation flow
**Files in scope:** `apps/whatsapp-agent/agents/whatsapp_agent/booking_tools.py`, one additive migration

---

## 1. Problem

During live testing, the agent confirmed an order (`LK-2026-000007`) **without first pausing to let the customer**:
1. add any additional notes / instructions, and
2. review the full details and confirm they are correct / choose to edit anything.

In the failing turn the agent called `get_order_summary` **and** `confirm_order` in the **same turn** (11:36:32) — i.e. it summarised and confirmed in one shot instead of showing the summary, asking the three review questions, and waiting for a separate explicit confirmation.

The desired behaviour is **already written into the system prompt** (`booking_tools.py:709–712`: *"Ask the customer to confirm the booking, add another note, or change anything. The order is confirmed only when they confirm the complete current summary."*). The note-capture system (`propose_order_note`, `get_active_order_notes`, `remove_order_note`) already exists. So this is a **reliability gap, not a missing feature** — the LLM did not follow an existing instruction.

## 2. Goal

Make the review step a **deterministic backend hard gate**: `confirm_order` is refused unless a complete order summary was shown to the customer in a **prior** turn (giving them a chance to respond), and any edit **re-arms** the gate so a changed order is always re-reviewed before confirmation.

Owner decisions (2026-07-31):
- **Enforcement:** backend hard gate (agent physically cannot skip the review).
- **Edit re-arms:** yes — any edit after the summary requires the summary to be re-shown and re-confirmed.

## 3. Non-Goals

- No change to what the summary *contains* (already correct).
- No new customer-facing copy beyond tightening the existing prompt lines.
- No change to the post-confirmation terminal boundary, facility auto-assign, CRM, or negotiation logic.
- Not building any new notes capability (already exists).

## 4. Design

### 4.1 State
Add one nullable column (additive migration, next number **000035**):

```
alter table orders add column review_summary_shown_at timestamptz;
```

`null` = no valid, un-edited summary has been shown → confirmation is blocked.

### 4.2 Arming the gate — `get_order_summary`
When `get_order_summary` runs and the order is complete enough to review, set the marker **only if not already set**, and record in-memory that it was *freshly* armed this turn:

```
if not row.get("review_summary_shown_at"):
    await _apply({"review_summary_shown_at": now()})
    review_freshly_armed_this_turn = True   # in-memory, per run_booking_turn invocation
```

"Only if not already set" avoids a confirm-loop: re-showing an unchanged summary in a later turn does not keep pushing the timestamp forward.

### 4.3 Edit re-arms — single choke point
`_apply(updates, state)` (`booking_tools.py:873`) is the **only** path that mutates an order. Make it clear the marker on any real content edit:

```
async def _apply(updates, state=None):
    # Any content edit invalidates a previously-shown review (owner: edit re-arms).
    if updates and set(updates) != {"review_summary_shown_at"}:
        updates = {**updates, "review_summary_shown_at": None}
    ...
```

Because every `save_*` / `add_item` / `negotiate_order_price` / note tool routes through `_apply`, this automatically re-arms the gate on **any** edit, with no per-tool wiring. The summary write itself (which sets the marker) is the single exception.

### 4.4 The gate — `confirm_order`
Before `ctx.repo.confirm_booking(...)` (`booking_tools.py:1366`):

```
if not row.get("review_summary_shown_at") or review_freshly_armed_this_turn:
    return _err(
        "REVIEW_REQUIRED — before confirming, show the FULL order summary (items, price, "
        "pickup date/time, full address, and any Additional Notes) and ask the customer to: "
        "(1) add any notes or special instructions, (2) check every detail is correct, and "
        "(3) tell you if they want to change anything. Confirm ONLY after they reply with an "
        "explicit yes in a later message. Do NOT confirm in the same turn you first show the summary."
    )
```

Truth table (with the in-memory `review_freshly_armed_this_turn` flag):

| Scenario | marker | freshly armed this turn | confirm |
|---|---|---|---|
| Never showed a summary | null | – | **blocked** |
| Summary + confirm same turn (first time) | set | yes | **blocked** |
| Summary turn N, confirm turn N+1 (no edit) | set | no | allowed |
| Edit in N+1 clears marker, re-show + confirm N+1 | set | yes | **blocked** |
| Edit in N+1, re-show N+1, confirm N+2 | set | no | allowed |

This needs no turn-id plumbing — the in-memory flag distinguishes "shown this turn" from "shown earlier."

### 4.5 Prompt tightening
Hoist the buried lines 709–712 into an imperative, prominent rule near the confirmation section: *"You MUST, in a PRIOR turn, have shown the full summary and asked: anything to add? / all correct? / change anything? — and received an explicit yes — before calling confirm_order. Never summarise and confirm in the same turn."* The backend gate is the safety net; the prompt keeps the UX natural.

## 5. Testing

Pure/uni tests around the tool executor (no live LLM / WhatsApp):
- same-turn `get_order_summary` → `confirm_order` returns `REVIEW_REQUIRED`, order stays draft.
- summary in turn N, confirm in turn N+1 → confirmed.
- edit (e.g. `save_pickup_time`) after summary clears `review_summary_shown_at`; confirm blocked until re-shown in a prior turn.
- confirm with no summary ever → blocked.
- idempotent duplicate confirm after a legitimately confirmed order → still `confirmed:true` (unchanged path).
- regression: existing booking/confirm/post-confirmation suites stay green.

## 6. Rollback

- Behaviour flag (e.g. `PRECONFIRM_REVIEW_GATE_ENABLED`, default true) so the gate can be disabled without a deploy.
- The column is additive and nullable; leaving it unused is harmless.

## 7. Risks / Notes

- **Friction:** a customer who says "just book it" still gets one review turn. That is the intended trade-off (owner chose the hard gate).
- **Migration drift:** dev/test Supabase must have 000035 applied (same asyncpg apply pattern as prior migrations) or the gate degrades — guard the column read so a missing column fails open to current behaviour, and log it.
- **Live end-to-end** verification requires a connected Evolution session; unit tests do not.
