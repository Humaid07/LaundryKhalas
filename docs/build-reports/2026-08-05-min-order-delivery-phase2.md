# Build Report — WhatsApp Agent Production Update, Phase 2a (Minimum Order + Delivery)

**Date:** 2026-08-05
**Status:** Section 12 implemented; full-suite verification in progress (see §5). UNCOMMITTED.

**Verification:** full backend suite (excluding the 3 pre-broken classifier test files)
**1356 passed, 0 failed, 0 errors** (`PYTEST_EXIT=0`).

## 1. Objective
Continue the phased 2026-08-05 update. Phase 2a delivers **Section 12 — minimum order +
delivery charge** (AED/QAR 30 free threshold, AED/QAR 10 flat fee), judged on the
pre-discount subtotal, with deterministic add-item / delivery-fee templates.

## 2. What changed
- **Config `config/fulfilment_charges.json`** (single source of truth): `free_delivery_min`
  **50 → 30** and `delivery_fee` **8 → 10** for both AE (AED) and QA (QAR). Version bumped to
  `2026-08-05.1`; note rewritten to the §12 rule.
- **`services/fulfilment.py`:**
  - Defaults updated (30 / 10).
  - `delivery_charge(order_total, *, market, threshold_total=None)` — the free/fee decision
    is now made on `threshold_total` (the **service subtotal before discount**, spec §12) when
    supplied, so a discount can never push an order below the free-delivery minimum; the fee is
    still added to the payable (post-discount) `order_total` for the grand total. Backward
    compatible (defaults to `order_total`).
  - New `evaluate_minimum_order(subtotal_before_discount, market) -> MinimumOrderStatus`
    (never rejects an order; reports below-minimum + figures).
  - New deterministic templates `minimum_order_add_item_text()` /
    `minimum_order_delivery_fee_text()` (spec §§12, 26) — currency + amount pulled from config
    so wording can never drift from the rule; both pass the reply-style validator (no emoji /
    exclamation / dash-prose).
- **`agents/whatsapp_agent/booking_tools.py`:**
  - Order summary passes `threshold_total=quote.eligible_subtotal` (pre-discount) to
    `delivery_charge`.
  - System prompt min-order rule rewritten: below the minimum, first ask to add an item; only
    if declined, state the flat fee up front; never reject a small order; never invent a fee.

## 3. Files
**Modified:** `config/fulfilment_charges.json`, `services/fulfilment.py`,
`agents/whatsapp_agent/booking_tools.py`, `tests/test_fulfilment_charges.py`,
`tests/test_stage3b_tools.py`, `tests/test_qa_pricing.py`.
**Created:** none (templates live in `fulfilment.py`; a full Section-26 template library is
deferred).
**Migrations:** none (config-driven).

## 4. Mock-only / live / deferred
- Mock-only: no live calls; delivery charge is backend-calculated and shown in the summary +
  grand total, stored in the quote snapshot.
- Deferred (still to come this phase): Stripe-first + cash-on-delivery flow (Section 13),
  payment / quote-inactivity / website-abandonment follow-up schedulers (Sections 14/24/25),
  the full versioned template library (Section 26), and wiring the min-order add-item prompt
  as a dedicated deterministic turn.

## 5. Tests
- Touched files in isolation: **green** (`test_fulfilment_charges` incl. new min-order/template
  tests, `test_stage3b_tools`, `test_qa_pricing`).
- New assertions: 30/10 thresholds; pre-discount threshold behavior; QA 45 ≥ 30 → free;
  below-min fee 10; template wording + style-validator cleanliness.
- **Full-suite result:** 1356 passed, 0 failed, 0 errors (classifier test files excluded).

### Test-infra fixes made during verification (beyond Section 12, but required for a
### trustworthy suite)
A long full run surfaced a `orders.order_id` demo-seed collision cascade that Phase 1's
faster run had not hit. Two real fixes:
1. **`services/order_store.py::seed_demo_orders` is now race-proof.** On the shared
   file-backed test DB a leaked connection from a webhook/turn test can insert a demo row
   between the existence check and the flush; the previous select-then-add lost that race and
   raised `UNIQUE(order_id)` during the *next* iteration's autoflush, breaking the autouse
   `_reset_orders` fixture and erroring whatever unrelated test was running. Each insert now
   runs in its own SAVEPOINT (`begin_nested`) and a collision is caught as "already seeded".
   This also removes the pending-add autoflush that was the actual crash site. Preserves the
   function's documented "idempotent, safe on every startup" contract.
2. **`tests/conftest.py` defaults `WHATSAPP_CLASSIFIER_ENABLED=false`** in the hermetic env
   (like the existing mock/sqlite pins). The internal intent classifier (separate uncommitted
   work) persists via raw SQL to `whatsapp_message_classifications`, a Supabase/migration-only
   table (000039) not in the sqlite ORM schema; left enabled its fail-open shadow hook fired on
   every webhook test, its insert hit a missing table, and the poisoned connection compounded
   the collisions.

**Known pre-existing (out-of-scope) issue:** the classifier's own 3 test files
(`test_classifier*.py`) still fail under sqlite because they exercise persistence to that
missing table. They need an ORM model / test fixture that creates it — the classifier work's
responsibility, flagged for its owner.

## 6. Security / privacy
- No new secrets. Confirmed the live `ANTHROPIC_API_KEY` in `apps/whatsapp-agent/.env` is
  **gitignored and never committed** (no commit touches `.env`; `git grep sk-ant-api03` across
  all history is empty) — correcting the Phase-1 report's "committed" wording.

## 7. Next
Section 13 (Stripe-first + cash-on-delivery) and the centralized follow-up scheduler
(Sections 14/24/25) — the largest greenfield build in the spec.
