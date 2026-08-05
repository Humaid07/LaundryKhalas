# Build Report — WhatsApp Agent Production Update, Phase 2b (Stripe-first Payment)

**Date:** 2026-08-05
**Status:** Section 13 complete end-to-end (engine + prompt + persistence + agent tool) and
**verified — full suite (minus 3 pre-broken classifier files) 1372 passed, 0 failed**.
Mock-only (no live Stripe). UNCOMMITTED.

## 1. Objective
Section 13 — Stripe-first payment behaviour. Stripe is the regular method; cash on delivery
is a bounded fallback offered only after the customer clearly declines the link. No live
Stripe integration (CLAUDE.md: no live Stripe unless approved) — this is the deterministic
decision engine + approved templates + prompt guidance.

## 2. What was built
- **`services/payment_preference.py`** (new, pure/deterministic):
  - `payment_preference` values `UNDECIDED | STRIPE | CASH_ON_DELIVERY`.
  - `PaymentState` (persisted fields: preference, stripe_preference_explained,
    stripe_no_account_explained, cash_requested, cash_accepted) and `PaymentDecision`.
  - `detect_payment_intent()` — classifies a message (cash / no-stripe / can't-use-link /
    emphatic-cash / chooses-stripe).
  - `resolve_payment_turn(state, text)` — the bounded escalation:
    1. first cash/payment question → **STRIPE_REGULAR_PAYMENT**
    2. no Stripe / can't use link → **STRIPE_ACCOUNT_NOT_REQUIRED**
    3. clear second refusal / emphatic "only cash" → **CASH_ON_DELIVERY_ACCEPTED**, stops.
    Positive "stripe is fine / send the link" → locks **STRIPE**. Never nags; never
    re-litigates once cash is accepted; a cash order can still switch to Stripe later.
  - Approved templates (spec §§13, 26): `STRIPE_REGULAR_PAYMENT`,
    `STRIPE_ACCOUNT_NOT_REQUIRED`, `CASH_ON_DELIVERY_ACCEPTED`, `STRIPE_CHOSEN_ACK` — short,
    no emoji/exclamation/dash (pass the reply-style validator).
- **Booking system prompt** (`booking_tools.py`): replaced the vague "prefer card, cash is
  fine" bullet with the explicit Stripe-first escalation + the exact three step templates and
  the "do not create a link yourself / never cash off-system" guardrails.
- **Persistence (backend-authoritative):**
  - Migration `000040` (`supabase/migrations/20260805_000040_orders_payment_preference.sql`) —
    adds `payment_preference` (checked: UNDECIDED|STRIPE|CASH_ON_DELIVERY),
    `stripe_preference_explained_at`, `stripe_no_account_explained_at`, `cash_requested_at`,
    `cash_accepted_at`, `payment_followup_stage` to `orders`. Idempotent.
  - `models.py` Order — the same columns for the SQLite ORM (so tests + `init_db` create them).
  - `payment_preference.state_from_row()` / `updates_for_state()` — pure mapping between the
    order row and `PaymentState`; a timestamp is stamped only on the first transition (never
    overwrites the original moment).
  - `orders_repo._BOOKING_COLS` — payment columns whitelisted so they persist through
    `apply_booking_updates`.
- **Agent tool `set_payment_preference`** (`booking_tools.py`, in `_WRITE_TOOLS`): the model
  passes the customer's exact payment message; the backend runs the engine on the PERSISTED
  state, saves the returned fields, and returns the approved `reply` for the model to send
  verbatim. The model never decides the method, creates a link, or invents wording.

## 3. Files
**Created:** `services/payment_preference.py`, `tests/test_payment_preference.py`,
`supabase/migrations/20260805_000040_orders_payment_preference.sql`.
**Modified:** `agents/whatsapp_agent/booking_tools.py` (prompt + `set_payment_preference`
tool), `models.py` (Order payment columns), `db/repositories/orders_repo.py`
(`_BOOKING_COLS`), `tests/test_agent_prompt_persona.py`, `tests/test_scenarios_regression.py`
(payment-prompt assertions), `tests/test_stage3b_tools.py` (payment tool tests).
**Migrations:** `000040` (orders payment columns) — **not applied** (apply to Supabase on deploy).

## 4. Tests
- `tests/test_payment_preference.py` — 10 tests: the three-step escalation, no third push,
  emphatic-cash shortcut, first-message-no-stripe, chooses-Stripe lock, non-payment
  passthrough, cash→Stripe switch, template style-safety. **Green.**
- Prompt regression fixtures updated to assert the Stripe-first text.
- Full suite (minus the 3 pre-broken classifier files): result appended on completion.

## 5. Mock-only / deferred
- **Mock-only:** no live Stripe; the engine never creates a payment link — for a Stripe order
  the backend sends the link via the established workflow (separate), for cash the order is
  marked cash on delivery.
- **Deferred to Phase 2c:**
  - A mock `create_stripe_payment_link` tool (the link is sent by the established post-processing
    workflow; no live Stripe in MVP) and surfacing payment state on the dashboards (Section 29).
  - **Payment follow-ups** when the customer goes silent (Section 14) — needs the centralized
    follow-up scheduler (no background-job infra exists yet); planned with Sections 24/25.

## 6. Security / privacy
- No secrets, no live external calls. Payment status remains backend-authoritative; the model
  never invents a payment state or link.

## 7. Next
Persist the payment state (migration 000040 + columns + tools), then build the centralized
follow-up scheduler (Sections 14/24/25) — payment-silence, quote-inactivity, website-abandonment.
