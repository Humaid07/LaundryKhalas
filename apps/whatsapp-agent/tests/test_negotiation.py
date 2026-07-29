"""Tests for the price-negotiation engine (founder-approved spec §3).

Covers the standard ladder (10→20 / 15→25), the tier boundary, the 5-minute ghost
window, the facility-floor formula with its itemisation guard, and the founder's
worked example. Pure/deterministic — no DB, no network.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from services import negotiation as neg


@pytest.fixture(autouse=True)
def _fresh_policy():
    neg.reload_policy()
    yield
    neg.reload_policy()


# --------------------------------------------------------------------------
# Tier selection (§3.1)
# --------------------------------------------------------------------------
@pytest.mark.parametrize("subtotal,expected", [
    (10, "low"),
    (60, "low"),
    (99.99, "low"),
    (100, "high"),      # boundary is inclusive of the high tier ('order >= 100')
    (100.01, "high"),
    (250, "high"),
])
def test_tier_boundary(subtotal, expected):
    assert neg.tier_for(subtotal) == expected


def test_ladders_by_tier():
    assert neg.ladder_for(60) == (Decimal("10"), Decimal("20"))
    assert neg.ladder_for(150) == (Decimal("15"), Decimal("25"))


def test_standard_max_percentage():
    assert neg.standard_max_percentage(60) == Decimal("20")
    assert neg.standard_max_percentage(150) == Decimal("25")


# --------------------------------------------------------------------------
# Ladder offers (§3.1) — each rung discounts the ORIGINAL subtotal, never stacks
# --------------------------------------------------------------------------
def test_low_tier_first_then_max_offer():
    first = neg.ladder_offer(60, 0)
    assert first.reason == "offered"
    assert first.percentage == Decimal("10")
    assert first.price == Decimal("54.00")     # 60 - 10%
    assert first.is_standard_max is False
    assert first.exhausted is False

    second = neg.ladder_offer(60, 1)
    assert second.percentage == Decimal("20")
    assert second.price == Decimal("48.00")    # 60 - 20% (off original, not off 54)
    assert second.is_standard_max is True


def test_high_tier_first_then_max_offer():
    first = neg.ladder_offer(200, 0)
    assert first.percentage == Decimal("15")
    assert first.price == Decimal("170.00")
    assert first.is_standard_max is False

    second = neg.ladder_offer(200, 1)
    assert second.percentage == Decimal("25")
    assert second.price == Decimal("150.00")
    assert second.is_standard_max is True


def test_ladder_exhausted_past_last_step():
    spent = neg.ladder_offer(60, 2)
    assert spent.reason == "exhausted"
    assert spent.exhausted is True
    assert spent.percentage is None
    assert spent.price is None


def test_ladder_invalid_inputs():
    assert neg.ladder_offer(0, 0).reason == "invalid"
    assert neg.ladder_offer(60, -1).reason == "invalid"


def test_ladder_offer_snapshot_is_loggable():
    snap = neg.ladder_offer(60, 1).to_snapshot()
    assert snap["kind"] == "ladder_offer"
    assert snap["percentage"] == 20.0
    assert snap["offered_price"] == 48.0
    assert snap["is_standard_max"] is True


# --------------------------------------------------------------------------
# Ghost timer (§3.1) — "no reply for more than 5 minutes"
# --------------------------------------------------------------------------
@pytest.mark.parametrize("seconds,expected", [
    (None, False),
    (0, False),
    (299, False),
    (300, False),       # exactly 5 min is NOT yet ghosted (strictly greater-than)
    (301, True),
    (600, True),
])
def test_ghost_window(seconds, expected):
    assert neg.is_ghosted(seconds) is expected


# --------------------------------------------------------------------------
# Facility-floor (§3.2) — floor = discounted - 0.75 × (discounted - facility_cost)
# --------------------------------------------------------------------------
def test_founder_worked_example():
    """Wash & Fold website 60 AED, <100 → 20% → 48; closest facility cost 30 →
    gap 18 → max concession 13.50 → absolute floor 34.50 (≈4.50 margin)."""
    max_offer = neg.ladder_offer(60, 1)
    assert max_offer.price == Decimal("48.00")

    floor = neg.facility_floor(max_offer.price, Decimal("30"), itemised=True)
    assert floor.allowed is True
    assert floor.reason == "ok"
    assert floor.max_concession == Decimal("13.50")
    assert floor.floor_price == Decimal("34.50")
    assert floor.margin_above_cost == Decimal("4.50")


def test_floor_blocked_without_itemisation():
    floor = neg.facility_floor(Decimal("48"), Decimal("30"), itemised=False)
    assert floor.allowed is False
    assert floor.reason == "needs_itemisation"
    assert floor.floor_price is None


def test_floor_blocked_without_facility_cost():
    for bad in (None, 0, Decimal("0")):
        floor = neg.facility_floor(Decimal("48"), bad, itemised=True)
        assert floor.allowed is False
        assert floor.reason == "no_facility_cost"


def test_floor_no_room_when_cost_meets_price():
    floor = neg.facility_floor(Decimal("48"), Decimal("50"), itemised=True)
    assert floor.allowed is True
    assert floor.reason == "no_room"
    assert floor.floor_price == Decimal("48.00")   # never below the discounted price


def test_floor_never_below_25_percent_of_gap_above_cost():
    """The floor always protects >=25% of the gap as margin above facility cost."""
    disc, cost = Decimal("100"), Decimal("40")
    floor = neg.facility_floor(disc, cost, itemised=True)
    gap = disc - cost                              # 60
    assert floor.floor_price == Decimal("55.00")   # 100 - 0.75*60
    assert (floor.floor_price - cost) >= gap * Decimal("0.25")


def test_floor_snapshot_carries_audit_cost():
    snap = neg.facility_floor(Decimal("48"), Decimal("30"), itemised=True).to_snapshot()
    assert snap["kind"] == "facility_floor"
    assert snap["floor_price"] == 34.5
    assert snap["facility_cost"] == 30.0           # audit log only, never customer-facing


# --------------------------------------------------------------------------
# Market overlay
# --------------------------------------------------------------------------
def test_qatar_market_uses_qar_currency():
    policy = neg.load_policy(market="QA")
    assert policy.currency == "QAR"
    assert policy.low_ladder == (Decimal("10"), Decimal("20"))


def test_unknown_market_falls_back_not_crashes():
    policy = neg.load_policy(market="ZZ")
    assert policy.currency in {"AED", "QAR"}


# --------------------------------------------------------------------------
# plan_offer — orchestration helper (ladder → floor → escalate)
# --------------------------------------------------------------------------
def test_plan_offer_first_then_second_rung_low_tier():
    d0 = neg.plan_offer(60)                     # nothing offered yet
    assert d0.action == "offer_ladder"
    assert d0.percentage == Decimal("10")
    assert d0.price == Decimal("54.00")
    assert d0.rule_code == "NEGOTIATED"

    d1 = neg.plan_offer(60, current_percentage=Decimal("10"))
    assert d1.percentage == Decimal("20")
    assert d1.price == Decimal("48.00")
    assert d1.is_standard_max is True


def test_plan_offer_high_tier_rungs():
    assert neg.plan_offer(200).percentage == Decimal("15")
    assert neg.plan_offer(200, current_percentage=Decimal("15")).percentage == Decimal("25")


def test_plan_offer_floor_when_itemised_and_cost_available():
    """After the standard max, an itemised order with a facility cost reaches the
    facility-floor (60 → 20% → 48; cost 30 → floor 34.50)."""
    d = neg.plan_offer(60, current_percentage=Decimal("20"),
                       itemised=True, facility_cost=Decimal("30"))
    assert d.action == "offer_floor"
    assert d.price == Decimal("34.50")
    assert d.rule_code == "NEG_FLOOR"


def test_plan_offer_asks_itemisation_when_not_itemised():
    d = neg.plan_offer(60, current_percentage=Decimal("20"),
                       itemised=False, facility_cost=Decimal("30"))
    assert d.action == "ask_itemisation"


def test_plan_offer_escalates_without_facility_cost():
    d = neg.plan_offer(60, current_percentage=Decimal("20"),
                       itemised=True, facility_cost=None)
    assert d.action == "escalate"


def test_plan_offer_below_floor_escalates():
    d = neg.plan_offer(60, current_percentage=Decimal("42.5"), current_rule_code="NEG_FLOOR")
    assert d.action == "escalate"
    assert d.reason == "below_floor"
