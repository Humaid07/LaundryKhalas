"""Follow-up scheduler orchestration (spec §§14, 24, 25) — the glue between the pure
policy engine (services/followups) and the durable queue (scheduled_followups).

Two halves, both pure so they unit-test offline:

  * SCHEDULING — builders that turn an event (payment silence, quote inactivity, an
    Order-Now click) into ready-to-persist ``scheduled_followups`` rows, with the due
    time computed by the policy and a ``dedupe_key`` guaranteeing at-most-once.
  * SWEEPING — ``plan_batch`` takes the PENDING/due rows + a suppression-context
    provider and returns at most ONE send per conversation (spec §25: only the most
    relevant follow-up). A thin sweeper script loads rows, calls this, sends via the
    provider, and marks rows SENT — no policy lives in the script.
"""
from __future__ import annotations

import datetime as _dt
from collections.abc import Callable
from dataclasses import dataclass

from services import followups

# scheduled_followups.status vocabulary (mirrors models.py / migration 000042).
PENDING = "PENDING"
SENT = "SENT"
CANCELLED = "CANCELLED"
SUPPRESSED = "SUPPRESSED"


# --- scheduling: build rows to persist --------------------------------------
def build_row(conversation_id, followup_type, anchor, *, market="AE", persona=None,
              order_id=None, customer_phone=None, dedupe_scope=None) -> dict:
    """A new ``scheduled_followups`` row (dict) ready to persist. ``due_at`` is computed
    by the policy (offset + 10 PM cutoff); ``dedupe_key`` makes it at-most-once.

    ``dedupe_scope`` is the identity the dedupe key is scoped to — normally the
    conversation, but for a website abandonment there is no conversation yet, so the web
    session id is used instead (and ``conversation_id`` stays None until linked)."""
    scope = dedupe_scope if dedupe_scope is not None else conversation_id
    return {
        "conversation_id": conversation_id,
        "order_id": order_id,
        "customer_phone": customer_phone,
        "followup_type": followup_type,
        "status": PENDING,
        "template_id": followup_type,
        "dedupe_key": followups.dedupe_key(scope, followup_type),
        "due_at": followups.compute_due_at(anchor, followup_type, market=market),
        "anchor_at": anchor,
        "market": market,
        "persona": persona,
    }


def payment_silence_rows(conversation_id, anchor, *, market="AE", persona=None,
                         order_id=None, customer_phone=None) -> list[dict]:
    """The two payment follow-ups (§14): Stripe nudge (~6 min) then cash offer (~15 min).
    Schedule when payment stays UNDECIDED and the customer goes silent; the sweeper's
    suppression drops them the moment they reply / pay / choose cash."""
    return [build_row(conversation_id, t, anchor, market=market, persona=persona,
                      order_id=order_id, customer_phone=customer_phone)
            for t in (followups.PAYMENT_STRIPE, followups.PAYMENT_CASH)]


def web_abandonment_rows(session_key, click_at, *, market="AE", persona=None,
                         customer_phone=None) -> list[dict]:
    """The three website Order-Now abandonment follow-ups (§24): 10 min, ~40 min (25%
    offer), +6 h. Only schedule for an identified, consented visitor. There is no
    conversation yet, so dedupe is scoped to the web ``session_key`` and the phone is
    the verified WhatsApp number the sweeper messages."""
    return [build_row(None, t, click_at, market=market, persona=persona,
                      customer_phone=customer_phone, dedupe_scope=session_key)
            for t in (followups.WEB_ABANDONMENT_1, followups.WEB_ABANDONMENT_2,
                      followups.WEB_ABANDONMENT_3)]


def quote_inactivity_row(conversation_id, quoted_at, *, market="AE", persona=None,
                         order_id=None, customer_phone=None) -> dict:
    """The single quote-inactivity follow-up (§25): ~6 min after an exact eligible quote."""
    return build_row(conversation_id, followups.QUOTE_INACTIVITY, quoted_at, market=market,
                     persona=persona, order_id=order_id, customer_phone=customer_phone)


def pickup_reminder_row(conversation_id, pickup_start, *, hours_before=2, market="AE",
                        persona=None, order_id=None, customer_phone=None) -> dict:
    """A pickup reminder due ``hours_before`` the pickup window start, shifted into the
    messaging window (unlike the anchor+offset follow-ups, this is slot-relative). One per
    conversation via the dedupe key. Schedule only for a future pickup."""
    anchor = pickup_start - _dt.timedelta(hours=hours_before)
    return build_row(conversation_id, followups.PICKUP_REMINDER, anchor, market=market,
                     persona=persona, order_id=order_id, customer_phone=customer_phone)


# --- sweeping: decide what to send ------------------------------------------
@dataclass(frozen=True)
class PlannedSend:
    followup_id: str
    conversation_id: str | None
    followup_type: str
    template_id: str | None
    text: str
    customer_phone: str | None


def _candidate(row: dict) -> followups.Candidate:
    return followups.Candidate(row["followup_type"], row["due_at"])


def plan_conversation(rows, ctx_by_type: dict, now: _dt.datetime, *, market="AE") -> PlannedSend | None:
    """From ONE conversation's PENDING rows, the single follow-up to send now (or None).
    Delegates the choice to the policy's ``select_next`` (due + in-window + un-suppressed
    → highest priority, earliest due)."""
    chosen = followups.select_next([_candidate(r) for r in rows], ctx_by_type, now, market=market)
    if chosen is None:
        return None
    matching = [r for r in rows if r["followup_type"] == chosen.followup_type]
    row = min(matching, key=lambda r: r["due_at"])
    text = followups.render(chosen.followup_type, row.get("persona"))
    if not text:
        return None
    return PlannedSend(
        followup_id=row["id"], conversation_id=row.get("conversation_id"),
        followup_type=chosen.followup_type, template_id=row.get("template_id"),
        text=text, customer_phone=row.get("customer_phone"),
    )


def plan_batch(rows, ctx_provider: Callable[[str | None, str], followups.SuppressionContext],
               now: _dt.datetime, *, market="AE") -> list[PlannedSend]:
    """From ALL PENDING rows across conversations, return at most ONE send per
    conversation (spec §25 — no overlapping nudges). ``ctx_provider(conversation_id,
    followup_type)`` yields the live suppression context for each row."""
    by_conv: dict = {}
    for r in rows:
        by_conv.setdefault(r.get("conversation_id"), []).append(r)
    plans: list[PlannedSend] = []
    for conv_id, conv_rows in by_conv.items():
        ctx_by_type = {r["followup_type"]: ctx_provider(conv_id, r["followup_type"]) for r in conv_rows}
        plan = plan_conversation(conv_rows, ctx_by_type, now, market=market)
        if plan is not None:
            plans.append(plan)
    return plans
