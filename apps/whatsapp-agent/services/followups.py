"""Centralized follow-up scheduler policy (spec §§14, 24, 25) — pure & deterministic.

One place decides WHEN a follow-up is due, WHETHER it may still be sent, and — when
several are due for the same customer — WHICH single one to send. This module does no
I/O and sends nothing; a thin sweeper persists/loads rows and calls the provider. Kept
pure so the timing, the 10 PM cutoff, the suppression rules and the "only the most
relevant follow-up" arbitration are all unit-testable offline.

Follow-up families:
  * PAYMENT_STRIPE / PAYMENT_CASH  — customer went silent mid payment-method talk (§14):
    ~6 min then ~15 min, at most two, never after a reply / payment / cash choice.
  * QUOTE_INACTIVITY               — silent ~6 min after an exact eligible quote (§25).
  * WEB_ABANDONMENT_1/2/3          — identified+consented Order-Now abandoner (§24):
    10 min, ~40 min (25% offer), +6 h; at most three; only if consented.
  * PICKUP_REMINDER                — operational reminder.

Timing offsets, the messaging window and the priority order live in
config/followups.json (never hardcoded).
"""
from __future__ import annotations

import datetime as _dt
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from services import clock

_CONFIG_FILE = Path(__file__).resolve().parent.parent / "config" / "followups.json"

# --- follow-up type constants ------------------------------------------------
PAYMENT_STRIPE = "PAYMENT_STRIPE"
PAYMENT_CASH = "PAYMENT_CASH"
QUOTE_INACTIVITY = "QUOTE_INACTIVITY"
DISCOUNT_OBJECTION = "DISCOUNT_OBJECTION"
WEB_ABANDONMENT_1 = "WEB_ABANDONMENT_1"
WEB_ABANDONMENT_2 = "WEB_ABANDONMENT_2"
WEB_ABANDONMENT_3 = "WEB_ABANDONMENT_3"
PICKUP_REMINDER = "PICKUP_REMINDER"

_PAYMENT_TYPES = frozenset({PAYMENT_STRIPE, PAYMENT_CASH})
_WEB_TYPES = frozenset({WEB_ABANDONMENT_1, WEB_ABANDONMENT_2, WEB_ABANDONMENT_3})

# --- approved follow-up templates (spec §§14, 24, 26) -----------------------
# Short, no emoji/exclamation/dash (pass the reply-style validator). {persona} is
# filled with the customer's PERSISTED persona at send time. The 25% figure is the
# only backend-approved abandonment offer (spec §24) and is applied via the discount
# engine when the customer responds — the message never promises a final total.
FOLLOWUP_TEMPLATES = {
    PAYMENT_STRIPE: "Would you like me to send the Stripe payment link?",
    PAYMENT_CASH: "It looks like Stripe may not be convenient. Shall I arrange cash on delivery?",
    QUOTE_INACTIVITY: "Would you like me to see if I can improve the price for you?",
    WEB_ABANDONMENT_1: ("Hi, I am {persona} from Laundry Khalas. I noticed you were about to "
                        "place an order. Would you like help booking it?"),
    WEB_ABANDONMENT_2: "I can offer 25% off an eligible standard order if you would like to continue.",
    WEB_ABANDONMENT_3: "Would you still like help arranging your laundry pickup?",
    PICKUP_REMINDER: "Quick reminder about your upcoming pickup. Is the timing still good for you?",
}


def render(followup_type: str, persona: str | None = None) -> str:
    """The approved customer-facing text for a follow-up, with the persona filled in.
    Returns '' for an unknown type (the caller then sends nothing)."""
    text = FOLLOWUP_TEMPLATES.get(followup_type, "")
    if "{persona}" in text:
        text = text.replace("{persona}", (persona or "").strip() or "Sara")
    return text


@lru_cache(maxsize=1)
def _config() -> dict:
    return json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))


def reload_config() -> None:
    """Drop the cached config (tests / after an edit)."""
    _config.cache_clear()


def offset_minutes(followup_type: str) -> int:
    return int(_config().get("offsets_minutes", {}).get(followup_type, 0))


def priority_rank(followup_type: str) -> int:
    """Lower = more relevant. Unknown types sort last."""
    order = _config().get("priority", [])
    return order.index(followup_type) if followup_type in order else len(order)


def dedupe_key(conversation_id: str | None, followup_type: str, *, anchor: str = "") -> str:
    """Stable idempotency key so a follow-up is scheduled/sent at most once."""
    return ":".join(str(p) for p in (conversation_id or "-", followup_type, anchor) if p != "")


# --- messaging window / 10 PM cutoff ----------------------------------------
def _window() -> tuple[int, int]:
    w = _config().get("messaging_window", {})
    return int(w.get("start_hour", 8)), int(w.get("cutoff_hour", 22))


def within_messaging_window(instant: _dt.datetime, *, market: str | None = None) -> bool:
    """True when the LOCAL-market time is inside [start_hour, cutoff_hour)."""
    start, cutoff = _window()
    local = clock.to_market(instant, market)
    return start <= local.hour < cutoff


def shift_into_window(instant: _dt.datetime, *, market: str | None = None) -> _dt.datetime:
    """Move a due time into the allowed window (spec §§14, 24: respect the 10 PM
    cutoff). Before the window start → this day's start; at/after the cutoff → the
    next day's start; otherwise unchanged. Returns a market-local aware datetime."""
    start, cutoff = _window()
    local = clock.to_market(instant, market)
    if local.hour < start:
        return local.replace(hour=start, minute=0, second=0, microsecond=0)
    if local.hour >= cutoff:
        nxt = local + _dt.timedelta(days=1)
        return nxt.replace(hour=start, minute=0, second=0, microsecond=0)
    return local


def compute_due_at(anchor: _dt.datetime, followup_type: str, *, market: str | None = None) -> _dt.datetime:
    """Due time for a follow-up: anchor + configured offset, shifted into the
    messaging window. ``anchor`` is the last relevant customer message (payment /
    quote) or the Order-Now click (web abandonment)."""
    due = anchor + _dt.timedelta(minutes=offset_minutes(followup_type))
    return shift_into_window(due, market=market)


# --- suppression -------------------------------------------------------------
@dataclass(frozen=True)
class SuppressionContext:
    """Everything that can cancel a pending follow-up (spec §§14, 24, 25). All
    default False so a caller only sets what applies."""
    customer_replied: bool = False       # customer responded since the anchor
    human_takeover: bool = False
    opted_out: bool = False
    already_sent: bool = False           # this exact follow-up already went out
    order_cancelled: bool = False
    provider_blocked: bool = False       # provider policy / outside allowed window
    # payment-specific
    paid: bool = False
    cash_selected: bool = False          # customer already chose cash
    # order / conversion
    order_confirmed: bool = False
    converted: bool = False              # web lead already became an order
    # website-abandonment consent gating
    consent_absent: bool = False
    invalid_number: bool = False


def is_suppressed(followup_type: str, ctx: SuppressionContext) -> tuple[bool, str | None]:
    """Whether a follow-up must NOT be sent, and why. Universal suppressors first,
    then per-family rules."""
    if ctx.customer_replied:
        return True, "customer_replied"
    if ctx.human_takeover:
        return True, "human_takeover"
    if ctx.opted_out:
        return True, "opted_out"
    if ctx.already_sent:
        return True, "already_sent"
    if ctx.order_cancelled:
        return True, "order_cancelled"
    if ctx.provider_blocked:
        return True, "provider_policy"

    if followup_type in _PAYMENT_TYPES:
        if ctx.paid:
            return True, "already_paid"
        if ctx.cash_selected:
            # Payment nudges only make sense while the method is undecided.
            return True, "cash_already_selected"
    if followup_type in _WEB_TYPES:
        if ctx.consent_absent or ctx.invalid_number:
            return True, "no_consent"
        if ctx.converted or ctx.order_confirmed:
            return True, "already_converted"
    if followup_type in (QUOTE_INACTIVITY, DISCOUNT_OBJECTION):
        if ctx.order_confirmed:
            return True, "already_ordered"
        if ctx.paid:
            return True, "already_paid"
    return False, None


# --- arbitration: only the most relevant follow-up (spec §25) ----------------
@dataclass(frozen=True)
class Candidate:
    followup_type: str
    due_at: _dt.datetime


def select_next(candidates, ctx_by_type: dict, now: _dt.datetime, *, market: str | None = None):
    """From the pending follow-ups for ONE customer, return the single one to send
    now, or None. A candidate is eligible when it is due (due_at <= now), inside the
    messaging window, and not suppressed by its context. Among eligible candidates
    the highest priority (lowest rank) wins; ties break on the earlier due time — so
    overlapping price / payment / abandonment nudges never all fire (spec §25)."""
    eligible = []
    for c in candidates:
        ctx = ctx_by_type.get(c.followup_type, SuppressionContext())
        if is_suppressed(c.followup_type, ctx)[0]:
            continue
        if c.due_at > now:
            continue
        if not within_messaging_window(now, market=market):
            continue
        eligible.append(c)
    if not eligible:
        return None
    return min(eligible, key=lambda c: (priority_rank(c.followup_type), c.due_at))
