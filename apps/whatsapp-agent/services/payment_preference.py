"""Stripe-first payment behaviour engine (spec §13) — pure & deterministic.

Stripe is the regular payment method; cash on delivery is the fallback offered only
after the customer clearly declines the link. The escalation is fixed and bounded so
the agent never nags:

  1. First payment/cash question  → explain Stripe is the regular method.
  2. Customer says they have no Stripe / can't use the link → explain no Stripe
     account is needed (pay by card through the link).
  3. Customer still declines (a clear second refusal, or an emphatic "only cash")
     → accept cash on delivery, and STOP pushing.

The backend owns the decision; the model never invents payment status. This module
takes the persisted payment state + the customer's latest message and returns the next
state + the approved deterministic reply. It performs NO I/O and creates NO payment
link (mock-first: no live Stripe). The caller persists the returned fields and, for a
Stripe order, triggers the established link workflow separately.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

# --- payment_preference values ----------------------------------------------
UNDECIDED = "UNDECIDED"
STRIPE = "STRIPE"
CASH_ON_DELIVERY = "CASH_ON_DELIVERY"

# --- deterministic templates (spec §§13, 26) --------------------------------
# Currency-agnostic, short, no emoji/exclamation/dash — pass the reply-style validator.
STRIPE_REGULAR_PAYMENT = "Our regular payment method is a Stripe link sent on WhatsApp."
STRIPE_ACCOUNT_NOT_REQUIRED = (
    "You do not need a Stripe account. You can pay by card through the link.")
CASH_ON_DELIVERY_ACCEPTED = "No problem. We can arrange cash on delivery."
STRIPE_CHOSEN_ACK = "Great choice. We will send the Stripe payment link once your order is ready."

TEMPLATES = {
    "STRIPE_REGULAR_PAYMENT": STRIPE_REGULAR_PAYMENT,
    "STRIPE_ACCOUNT_NOT_REQUIRED": STRIPE_ACCOUNT_NOT_REQUIRED,
    "CASH_ON_DELIVERY_ACCEPTED": CASH_ON_DELIVERY_ACCEPTED,
    "STRIPE_CHOSEN_ACK": STRIPE_CHOSEN_ACK,
}

# --- customer payment-intent detection --------------------------------------
_CASH = re.compile(
    r"\b(cash|cod|pay on (?:delivery|collection|arrival)|"
    r"pay (?:when|on) (?:you |the driver )?(?:deliver|arrive|come)|"
    r"pay in person|pay by hand)\b", re.IGNORECASE)
_NO_STRIPE = re.compile(
    r"\b(no stripe|don'?t have (?:a )?stripe|do not have (?:a )?stripe|"
    r"without stripe|not on stripe|haven'?t got stripe|no stripe account)\b",
    re.IGNORECASE)
_CANT_USE_LINK = re.compile(
    r"\b(can'?t use (?:the )?link|cannot use (?:the )?link|link (?:doesn'?t|does not) work|"
    r"no card|don'?t have (?:a )?card|no online payment|can'?t pay online)\b",
    re.IGNORECASE)
_EMPHATIC_CASH = re.compile(
    r"\b(only cash|just cash|cash only|must be cash|insist|prefer cash|"
    r"rather (?:pay )?cash|i want cash|i'?ll pay cash|cash please)\b", re.IGNORECASE)
_CHOOSES_STRIPE = re.compile(
    r"\b(stripe is fine|stripe works|send (?:me )?the link|share the link|"
    r"pay by card|card is fine|card works|(?:ok(?:ay)?|yes|sure|fine)[, ]+(?:stripe|link|card)|"
    r"i'?ll use stripe|use stripe|the link is fine|online is fine)\b", re.IGNORECASE)


@dataclass(frozen=True)
class PaymentState:
    """The persisted payment conversation state for an order (all default to the
    fresh/undecided values)."""
    preference: str = UNDECIDED
    stripe_preference_explained: bool = False
    stripe_no_account_explained: bool = False
    cash_requested: bool = False
    cash_accepted: bool = False


@dataclass(frozen=True)
class PaymentDecision:
    """The outcome of one payment turn: which approved reply to send, the new
    persisted state, and whether the flow should stop discussing payment."""
    template_id: str | None
    text: str | None
    state: PaymentState
    stop_pushing: bool
    handled: bool  # True when the message was a payment-method signal we acted on


def detect_payment_intent(text: str | None) -> dict:
    """Classify a customer message for payment signals (pure). Multiple flags can
    be true (e.g. 'I don't have stripe, only cash')."""
    t = text or ""
    return {
        "cash": bool(_CASH.search(t)) or bool(_EMPHATIC_CASH.search(t)),
        "no_stripe": bool(_NO_STRIPE.search(t)),
        "cant_use_link": bool(_CANT_USE_LINK.search(t)),
        "emphatic_cash": bool(_EMPHATIC_CASH.search(t)),
        "chooses_stripe": bool(_CHOOSES_STRIPE.search(t)),
    }


def resolve_payment_turn(state: PaymentState, text: str | None) -> PaymentDecision:
    """Advance the Stripe-first escalation by one turn.

    Returns handled=False (and no template) when the message carries no payment
    signal, so the caller leaves payment handling to the normal flow.
    """
    intent = detect_payment_intent(text)
    signals_cash = intent["cash"] or intent["no_stripe"] or intent["cant_use_link"]

    # Customer positively chose the card/link — lock STRIPE, stop pushing.
    if intent["chooses_stripe"] and not signals_cash:
        new = PaymentState(
            preference=STRIPE,
            stripe_preference_explained=state.stripe_preference_explained,
            stripe_no_account_explained=state.stripe_no_account_explained,
            cash_requested=state.cash_requested,
            cash_accepted=state.cash_accepted,
        )
        return PaymentDecision("STRIPE_CHOSEN_ACK", STRIPE_CHOSEN_ACK, new,
                               stop_pushing=True, handled=True)

    if not signals_cash:
        return PaymentDecision(None, None, state, stop_pushing=False, handled=False)

    # Already settled on cash — never re-litigate.
    if state.preference == CASH_ON_DELIVERY:
        return PaymentDecision(None, None, state, stop_pushing=True, handled=True)

    # A clear second refusal, an emphatic "only cash", or a can't-use-link after we
    # have already explained the link → accept cash and stop pushing.
    second_refusal = state.stripe_no_account_explained or (
        state.stripe_preference_explained and (intent["emphatic_cash"] or intent["cant_use_link"]))
    if second_refusal:
        new = PaymentState(
            preference=CASH_ON_DELIVERY,
            stripe_preference_explained=state.stripe_preference_explained,
            stripe_no_account_explained=state.stripe_no_account_explained,
            cash_requested=True, cash_accepted=True,
        )
        return PaymentDecision("CASH_ON_DELIVERY_ACCEPTED", CASH_ON_DELIVERY_ACCEPTED,
                               new, stop_pushing=True, handled=True)

    # Second mention (we already explained Stripe once) OR the customer specifically
    # cites not having a Stripe account → explain no account is needed.
    if state.stripe_preference_explained or intent["no_stripe"]:
        new = PaymentState(
            preference=UNDECIDED,
            stripe_preference_explained=True,
            stripe_no_account_explained=True,
            cash_requested=True, cash_accepted=state.cash_accepted,
        )
        return PaymentDecision("STRIPE_ACCOUNT_NOT_REQUIRED", STRIPE_ACCOUNT_NOT_REQUIRED,
                               new, stop_pushing=False, handled=True)

    # First payment/cash question → explain Stripe is the regular method.
    new = PaymentState(
        preference=UNDECIDED,
        stripe_preference_explained=True,
        stripe_no_account_explained=state.stripe_no_account_explained,
        cash_requested=True, cash_accepted=state.cash_accepted,
    )
    return PaymentDecision("STRIPE_REGULAR_PAYMENT", STRIPE_REGULAR_PAYMENT,
                           new, stop_pushing=False, handled=True)


# --- persistence mapping (order row <-> PaymentState) -----------------------
def wants_payment_followups(decision: PaymentDecision) -> bool:
    """True when a payment turn should ARM the silence follow-ups (§14): the customer is
    actively discussing the method but has NOT settled — still UNDECIDED and we are not
    stopping. Once cash/stripe is chosen (stop_pushing) or the message wasn't a payment
    signal, no follow-up is scheduled."""
    return bool(decision.handled
                and decision.state.preference == UNDECIDED
                and not decision.stop_pushing)


def state_from_row(row: dict | None) -> PaymentState:
    """Reconstruct the payment state from a persisted order row. The *_at
    timestamps double as the boolean flags (non-null = it happened)."""
    row = row or {}
    return PaymentState(
        preference=(row.get("payment_preference") or UNDECIDED),
        stripe_preference_explained=row.get("stripe_preference_explained_at") is not None,
        stripe_no_account_explained=row.get("stripe_no_account_explained_at") is not None,
        cash_requested=row.get("cash_requested_at") is not None,
        cash_accepted=row.get("cash_accepted_at") is not None,
    )


def updates_for_state(prev_row: dict | None, state: PaymentState, now: datetime) -> dict:
    """The order-column updates to persist ``state``. A timestamp is stamped only
    when its flag flips true for the first time (so we never overwrite the original
    moment on a re-run); ``payment_preference`` is always written."""
    prev = prev_row or {}
    updates: dict = {"payment_preference": state.preference}

    def _stamp(col: str, flag: bool) -> None:
        if flag and prev.get(col) is None:
            updates[col] = now

    _stamp("stripe_preference_explained_at", state.stripe_preference_explained)
    _stamp("stripe_no_account_explained_at", state.stripe_no_account_explained)
    _stamp("cash_requested_at", state.cash_requested)
    _stamp("cash_accepted_at", state.cash_accepted)
    return updates
