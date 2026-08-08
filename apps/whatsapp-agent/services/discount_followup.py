"""Send-time decision for the 5-7 minute discount-objection follow-up (spec §8/§9).

When a DISCOUNT_OBJECTION follow-up comes due, the backend — never the AI — decides
what happens by re-running the deterministic negotiation engine for the order's
current state (the ~6 min wait means the negotiation ghost window has elapsed, so the
ladder may advance one rung):

  * send    — an eligible offer exists; send the backend-computed offer text.
  * review  — nothing more may be offered (ceiling / margin floor) → conversion review.
  * suppress— not eligible right now (needs itemisation, inactive, or the quote the
              customer saw has since changed) → drop the follow-up quietly.

The AI never picks the percentage; `percentage`/`price` come straight from
negotiation.plan_offer. Pure, no I/O.
"""
from __future__ import annotations

from dataclasses import dataclass

from services import money, negotiation

SEND = "send"
REVIEW = "review"
SUPPRESS = "suppress"

# Conversion-review reasons (spec §9).
DISCOUNT_LIMIT_REACHED = "DISCOUNT_LIMIT_REACHED"
PRICE_OBJECTION_MARGIN_LIMIT = "PRICE_OBJECTION_MARGIN_LIMIT"


@dataclass(frozen=True)
class DiscountFollowupDecision:
    kind: str                      # SEND | REVIEW | SUPPRESS
    text: str | None = None        # customer message when kind == SEND
    percentage: float | None = None
    price: float | None = None
    reason: str | None = None      # SUPPRESS reason or REVIEW reason


def _offer_text(percentage, price, currency: str) -> str:
    pct = int(percentage) if percentage == int(percentage) else percentage
    return (f"I checked again and I can offer you {pct}% off, "
            f"which brings it to {currency} {money.format_money(price)}.")


def decide(*, subtotal, current_percentage=None, current_rule_code=None,
           itemised: bool = False, facility_cost=None,
           stored_quote_version=None, current_quote_version=None,
           currency: str = "AED", policy=None) -> DiscountFollowupDecision:
    """Decide what the due discount-objection follow-up should do."""
    # Guard: never re-offer against a quote the customer no longer sees.
    if (stored_quote_version is not None and current_quote_version is not None
            and stored_quote_version != current_quote_version):
        return DiscountFollowupDecision(SUPPRESS, reason="quote_changed")

    decision = negotiation.plan_offer(
        subtotal, current_percentage=current_percentage, current_rule_code=current_rule_code,
        itemised=itemised, facility_cost=facility_cost, policy=policy)

    if decision.action in ("offer_ladder", "offer_floor"):
        return DiscountFollowupDecision(
            SEND, text=_offer_text(decision.percentage, decision.price, currency),
            percentage=float(decision.percentage) if decision.percentage is not None else None,
            price=float(decision.price) if decision.price is not None else None)

    if decision.action == "escalate":
        # below_floor / no_room = margin limit; no_ladder / spent ladder = discount ceiling.
        review_reason = (PRICE_OBJECTION_MARGIN_LIMIT
                         if decision.reason in ("below_floor", "no_room", "no_facility_cost")
                         else DISCOUNT_LIMIT_REACHED)
        return DiscountFollowupDecision(REVIEW, reason=review_reason)

    if decision.action == "ask_itemisation":
        # Standard ladder is spent and a deeper (floor) price needs the item list — which
        # a silent follow-up cannot solicit. The customer is hesitant at the standard max,
        # so hand it to a human rather than dropping it.
        return DiscountFollowupDecision(REVIEW, reason=DISCOUNT_LIMIT_REACHED)

    # inactive / invalid → nothing safe to send now.
    return DiscountFollowupDecision(SUPPRESS, reason=decision.reason)
