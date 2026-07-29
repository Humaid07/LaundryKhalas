"""Tests for the Express surcharge + same-day cut-off engine (spec §2.4)."""
from __future__ import annotations

import datetime as _dt
from decimal import Decimal

import pytest

from services import delivery

WASH_FOLD = "WASH_FOLD_6KG"
SHOE = "SHOE_CARE_SPORTS_SNEAKERS"


@pytest.fixture(autouse=True)
def _fresh():
    delivery.reload_sla()
    yield
    delivery.reload_sla()


def test_surcharge_is_50_percent():
    assert delivery.express_surcharge_pct() == Decimal("0.5")
    assert delivery.apply_express_surcharge(Decimal("100")) == Decimal("150.00")
    assert delivery.apply_express_surcharge(Decimal("63")) == Decimal("94.50")


def test_cutoff_is_3pm():
    assert delivery.express_cutoff_local() == "15:00"


@pytest.mark.parametrize("hour,minute,after", [
    (14, 59, False),
    (15, 0, False),      # exactly 3 PM is still within cut-off (strictly greater-than)
    (15, 1, True),
    (18, 30, True),
])
def test_after_cutoff(hour, minute, after):
    now = _dt.datetime(2026, 7, 29, hour, minute)
    assert delivery.is_after_express_cutoff(now) is after


def test_express_quote_before_cutoff_no_facility_check():
    now = _dt.datetime(2026, 7, 29, 11, 0)
    q = delivery.express_quote([WASH_FOLD], Decimal("100"), now)
    assert q.eligible is True
    assert q.after_cutoff is False
    assert q.requires_facility_check is False
    assert q.express_total == Decimal("150.00")
    assert q.surcharge_amount == Decimal("50.00")


def test_express_quote_after_cutoff_requires_facility_check():
    """Post-3PM is NOT auto-rejected: it flags a facility capacity check (spec §2.4)."""
    now = _dt.datetime(2026, 7, 29, 16, 30)
    q = delivery.express_quote([WASH_FOLD], Decimal("100"), now)
    assert q.eligible is True
    assert q.after_cutoff is True
    assert q.requires_facility_check is True


def test_ineligible_order_has_no_facility_check():
    now = _dt.datetime(2026, 7, 29, 16, 30)
    q = delivery.express_quote([WASH_FOLD, SHOE], Decimal("100"), now)
    assert q.eligible is False
    assert q.requires_facility_check is False


def test_express_quote_snapshot_loggable():
    now = _dt.datetime(2026, 7, 29, 11, 0)
    snap = delivery.express_quote([WASH_FOLD], Decimal("100"), now).to_snapshot()
    assert snap["surcharge_pct"] == 0.5
    assert snap["express_total"] == 150.0
