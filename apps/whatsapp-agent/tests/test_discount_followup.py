"""Phase 3: send-time decision for the discount-objection follow-up (spec §8/§9)."""
from decimal import Decimal

import pytest

from services import discount_followup as df
from services import negotiation


@pytest.fixture(autouse=True)
def _fresh_policy():
    negotiation.reload_policy()
    yield
    negotiation.reload_policy()


def test_fresh_order_sends_backend_offer():
    # subtotal 120 (>100 -> high ladder [15,25]); nothing offered yet -> first rung 15%.
    d = df.decide(subtotal=Decimal("120"), current_percentage=None, currency="AED")
    assert d.kind == df.SEND
    assert d.percentage == 15.0
    assert "15% off" in d.text
    assert "AED" in d.text


def test_ceiling_reached_triggers_review_not_offer():
    # already at standard max (25% on high ladder), not itemised, no facility cost -> escalate.
    d = df.decide(subtotal=Decimal("120"), current_percentage=Decimal("25"),
                  current_rule_code="NEGOTIATED", itemised=False, facility_cost=None)
    assert d.kind == df.REVIEW
    assert d.reason in (df.DISCOUNT_LIMIT_REACHED, df.PRICE_OBJECTION_MARGIN_LIMIT)


def test_below_floor_triggers_margin_review():
    d = df.decide(subtotal=Decimal("120"), current_percentage=Decimal("25"),
                  current_rule_code="NEG_FLOOR")
    assert d.kind == df.REVIEW
    assert d.reason == df.PRICE_OBJECTION_MARGIN_LIMIT


def test_quote_changed_suppresses():
    d = df.decide(subtotal=Decimal("120"), stored_quote_version=1, current_quote_version=2)
    assert d.kind == df.SUPPRESS
    assert d.reason == "quote_changed"


def test_ai_never_picks_number_offer_comes_from_engine():
    d = df.decide(subtotal=Decimal("120"), current_percentage=None)
    # percentage equals the negotiation engine's ladder rung, not an arbitrary value
    expected = negotiation.plan_offer(Decimal("120"), current_percentage=None).percentage
    assert d.percentage == float(expected)
