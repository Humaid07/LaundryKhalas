"""Tests for the minimum-order / delivery-charge engine (spec §2.3)."""
from __future__ import annotations

from decimal import Decimal

import pytest

from services import fulfilment


@pytest.fixture(autouse=True)
def _fresh():
    fulfilment.reload_charges()
    yield
    fulfilment.reload_charges()


@pytest.mark.parametrize("total,free,fee", [
    (10, False, Decimal("8.00")),
    (49.99, False, Decimal("8.00")),
    (50, True, Decimal("0.00")),        # exactly the minimum ships free (>=)
    (50.01, True, Decimal("0.00")),
    (250, True, Decimal("0.00")),
])
def test_delivery_charge_threshold(total, free, fee):
    result = fulfilment.delivery_charge(total)
    assert result.free is free
    assert result.fee == fee


def test_grand_total_includes_fee_below_min():
    result = fulfilment.delivery_charge(Decimal("30"))
    assert result.fee == Decimal("8.00")
    assert result.order_grand_total == Decimal("38.00")


def test_grand_total_equals_total_when_free():
    result = fulfilment.delivery_charge(Decimal("120"))
    assert result.order_grand_total == Decimal("120.00")


def test_currency_from_market():
    assert fulfilment.delivery_charge(30, market="AE").currency == "AED"
    assert fulfilment.delivery_charge(30, market="QA").currency == "QAR"


def test_snapshot_is_loggable():
    snap = fulfilment.delivery_charge(30).to_snapshot()
    assert snap["delivery_free"] is False
    assert snap["delivery_fee"] == 8.0
    assert snap["order_grand_total"] == 38.0
