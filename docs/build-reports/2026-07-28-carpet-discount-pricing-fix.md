# Build Report — Carpet/rug discount: measured-estimate pricing, authoritative discount tool, tone

**Date:** 2026-07-28

## Objective
A customer quoted ~AED 600 for a 30 sqm carpet then asked for the best price. The
agent stayed defensive, kept AED 600 active, and said the discount would apply
"later". Required outcome: one **20%** discount (AED 600 > 200), **−AED 120**,
revised **AED 480**, applied immediately, persisted everywhere, with a calm,
non-defensive reply.

## Reproduction + trace (before any change)
`pricing.calculate_estimate([carpet 30 sqm], discount_requested=True)` returned
`discount_applied=False, reason="unknown_total", customer_total=600.0`.

- **Discount intent classification:** OK — `discount.detect_discount_request` fires
  on "best price / cheaper / expensive …", and the webhook stored `discount_requested=True` (sticky).
- **Was the pricing tool called / did the 20% rule exist?** The 20% rule exists and
  600 > 200, **but it was never evaluated.**
- **Root cause (pricing engine):** a per-sqm carpet with a supplied measurement is a
  *measured estimate* → `has_measured_estimate=True` → `is_final=False`.
  `calculate_estimate` passed `total_is_known=quote.is_final` to `discount.evaluate`,
  so a *measured* estimate was treated as an *unknown* total and the discount was
  skipped entirely. The engine returned 600.
- **Persistence:** the webhook set the `discount_requested` flag but **did not
  re-price** the draft, so `estimated_total` stayed at the pre-discount value.
- **LLM prompt:** the stable prompt literally instructed *"Once your order is
  confirmed, any eligible discount is applied automatically"* and *"do NOT promise a
  specific discount before the exact total is known"* → the deferring/defensive tone.

So the failure was **primarily the backend pricing engine**, compounded by a
**persistence gap** and a **prompt** that deferred the discount. Not tool-selection.

## Fix
1. **Pricing engine (`services/pricing.py`)** — decoupled discount eligibility from
   the "final" label. A measured estimate has a **known** amount (rate × sqm), so it
   now qualifies; only genuinely-unknown `pending` ('from'/inspection) lines are
   excluded (`total_is_known = not has_pending and subtotal > 0`). `is_final`
   (labelling) is unchanged, so the total is still shown as ESTIMATED.
2. **Authoritative tool `calculate_applicable_order_discount`
   (`agents/whatsapp_agent/booking_tools.py`)** — the backend computes the single
   applicable rule (never the model), persists the re-priced FINAL total to the draft,
   and returns `{eligible, applied_discount_rule_code, applied_percentage,
   pre_discount_total, discount_amount, final_total, currency, calculation_version,
   reason_code, pricing_status, customer_safe_summary}`. Idempotent (never stacks).
3. **Re-price on request (`api/evolution_webhooks.py` + `booking_flow.pricing_updates_for_row`)**
   — when a discount request is detected mid-conversation, the draft is re-priced and
   the FINAL total persisted immediately, so no stale pre-discount amount survives.
4. **System prompt** — rewrote the price-objection guidance: acknowledge → call the
   tool → state the revised `final_total` → **one** calm question. Explicitly forbids
   "applied later/after confirmation", "fixed rate", "you don't need to ask", arguing,
   policy over-explaining, and repeated "would you like to proceed?".
5. **WhatsApp summary (`services/pricing.py`)** — now shows `Original estimate: AED 600`
   / `Special 20% discount: -AED 120` / `Revised estimated price: AED 480`. No VAT line.

## Rule-code note
The repo's existing rule code is **`ORDER_OVER_200_DISCOUNT_REQUESTED`** — this **is**
the task's `DISCOUNT_REQUEST_OVER_200` (behaviour identical: >200 + request → 20%). It
was **not** renamed, to preserve the established snapshot contract/tests.

## Money model
All money is `Decimal` HALF-UP via `services/money.py`; published prices are already
VAT-inclusive (no ×1.05); the customer-facing amount is the post-discount final. No
customer-facing VAT/tax wording anywhere (verified in tests).

## Files changed
- `services/pricing.py` (eligibility decoupled from label; summary wording)
- `agents/whatsapp_agent/booking_tools.py` (new tool + `_fmt_pct` + prompt)
- `services/booking_flow.py` (`pricing_updates_for_row` re-price helper)
- `api/evolution_webhooks.py` (re-price on detected request + logging)
- `tests/test_order_discount.py`, `tests/test_booking_tools.py` (tests + updated wording assertion)

## Database
**No schema change.** The discount snapshot columns already exist
(`eligible_subtotal`, `discount_rule_code`, `discount_percentage`, `discount_threshold`,
`discount_amount`, `discount_requested`) with `estimated_total`/`amount` as the FINAL
payable. `pricing_status` (ESTIMATED/CONFIRMED) is derived from `is_estimated` (persisted
`pricing_is_estimated`) — no new column needed.

## Dashboard
Data verified: `orders_repo.to_read(...).pricing` returns `final_price=480.0`,
`discount_applied=True`, `discount_amount=120`, `discount_percentage=20`,
`eligible_subtotal=600`. The admin app already renders `pricing.final_price`, so the
list/detail show AED 480 with the authorized breakdown. No admin UI file was changed
this pass (separate Next.js app; data contract already correct).

## Payment / Stripe
**Stripe is not integrated in this repo (mock/off — CLAUDE.md §5).** The payable amount
(`order.amount` / `estimated_total`) is 480 everywhere, which any future Stripe session
must use. Live Stripe Checkout/PaymentIntent/receipt and old-link supersession/
invalidation are **out of scope / require explicit approval** and were **not** faked.

## Logging
Added structured events (safe ids + numeric amounts, no PII/secrets):
`discount_request_detected`, `discount_rule_resolved`, `discount_applied` /
`discount_not_applied`, `order_total_recalculated` (webhook) and `discount_applied` /
`discount_not_applied` (tool).

## Tests + results
- Engine precedence (100/100.01/200/200.01, non-stacking, idempotent) — existing, pass.
- **New:** measured carpet matrix (600→480, 500→400, 200→170, 100→none, 600 no-request→510),
  spec-scenario assertion (rule/120/480 + summary wording + no VAT), engine idempotency,
  and the `calculate_applicable_order_discount` tool (structured output + persisted 480 + idempotent).
- Updated the summary test to the new wording.
- **138 targeted tests pass** (order_discount, booking_tools, final_pricing,
  catalogue_pricing, pricing_management, orchestration_delivery). ruff clean.
- **Live end-to-end vs dev Supabase** (real executor + repos): carpet 30 sqm → tool →
  confirm → draft, order, and dashboard read model **all AED 480**; facility assigned;
  test rows cleaned up.

## Manual verification
Over WhatsApp: book a 30 sqm carpet (quote shows AED 600, or AED 510 after the automatic
15%), then send "best price?". The agent replies acknowledging + "20% discount → revised
AED 480" + one question. Internal dashboard (Operations → Customer Orders) and the order
detail show **AED 480** with the 20% / −120 breakdown.

## Known limitations / honestly deferred
- **Real Stripe** (charge 480, link supersession) — not integrated; payable field is 480.
- **Explicit immutable pricing-audit table on measurement edits** — recalculation is
  deterministic and the discount snapshot is persisted; an append-only audit row per
  re-price is a documented follow-up (order lifecycle is already captured in `order_events`).
- **Admin UI restyle** ("prominent" display) — data is correct; no UI file changed.
- **Behaviour change:** measured estimates over AED 100 now also receive the automatic
  15% tier even without a request (matching how exact orders already behaved and the
  stated precedence) — e.g. a 600 carpet shows 510 before any request.
- **No CRM/HubSpot** added or referenced (per instruction); all data stays in the
  Laundry Khalaas backend/DB/dashboard.
