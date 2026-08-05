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
    (10, False, Decimal("10.00")),
    (29.99, False, Decimal("10.00")),
    (30, True, Decimal("0.00")),        # exactly the minimum ships free (>=)
    (30.01, True, Decimal("0.00")),
    (250, True, Decimal("0.00")),
])
def test_delivery_charge_threshold(total, free, fee):
    result = fulfilment.delivery_charge(total)
    assert result.free is free
    assert result.fee == fee


def test_grand_total_includes_fee_below_min():
    result = fulfilment.delivery_charge(Decimal("20"))
    assert result.fee == Decimal("10.00")
    assert result.order_grand_total == Decimal("30.00")


def test_grand_total_equals_total_when_free():
    result = fulfilment.delivery_charge(Decimal("120"))
    assert result.order_grand_total == Decimal("120.00")


def test_threshold_uses_pre_discount_subtotal_when_given():
    # Post-discount payable is 25 (below 30) but the pre-discount subtotal is 40 →
    # still FREE (spec §12: the minimum is judged before discount).
    result = fulfilment.delivery_charge(Decimal("25"), threshold_total=Decimal("40"))
    assert result.free is True
    assert result.fee == Decimal("0.00")
    assert result.order_grand_total == Decimal("25.00")


def test_currency_from_market():
    assert fulfilment.delivery_charge(30, market="AE").currency == "AED"
    assert fulfilment.delivery_charge(30, market="QA").currency == "QAR"


def test_snapshot_is_loggable():
    snap = fulfilment.delivery_charge(20).to_snapshot()
    assert snap["delivery_free"] is False
    assert snap["delivery_fee"] == 10.0
    assert snap["order_grand_total"] == 30.0


# --- minimum-order evaluation + deterministic templates (spec §§12, 26) ------
def test_evaluate_minimum_order_below_and_at_threshold():
    below = fulfilment.evaluate_minimum_order(20)
    assert below.below_minimum is True and below.minimum == Decimal("30.00")
    assert below.delivery_fee == Decimal("10.00")
    at = fulfilment.evaluate_minimum_order(30)
    assert at.below_minimum is False


def test_minimum_order_templates_are_grounded_and_clean():
    from services.reply_style import normalize_customer_reply
    add = fulfilment.minimum_order_add_item_text("AE")
    fee = fulfilment.minimum_order_delivery_fee_text("AE")
    assert "AED 30" in add and "add another item" in add
    assert "AED 10" in fee
    qa = fulfilment.minimum_order_add_item_text("QA")
    assert "QAR 30" in qa
    # No emoji / exclamation / dash-prose: the style validator leaves them unchanged.
    for t in (add, fee, qa):
        assert normalize_customer_reply(t).text == t
