"""Automatic 15%-over-AED-100 order discount (task spec §§5-11, tests 13-30).

Hermetic: pure Decimal engine (services.discount) + the quote engine
(services.pricing) over the static catalogue. No DB, no network.
"""
from decimal import Decimal

import pytest

from services import discount, pricing


# --- Pure engine: threshold is STRICTLY greater-than (spec §5) ---------------
@pytest.mark.parametrize("subtotal, applied, amount, final", [
    ("99",     False, "0.00",  "99.00"),    # below threshold
    ("100",    False, "0.00",  "100.00"),   # AT threshold -> NO discount (spec §5/§7)
    ("100.01", True,  "15.00", "85.01"),    # just over -> 15%
    ("120",    True,  "18.00", "102.00"),   # spec §7 example
    ("150",    True,  "22.50", "127.50"),   # spec §7 example
])
def test_threshold_and_amounts(subtotal, applied, amount, final):
    r = discount.evaluate(Decimal(subtotal))
    assert r.applied is applied
    assert r.discount_amount == Decimal(amount)
    assert r.final_total == Decimal(final)
    assert isinstance(r.discount_amount, Decimal)   # Decimal math (spec §6)


def test_zero_and_negative_never_discounted():
    assert discount.evaluate(Decimal("0")).applied is False
    assert discount.evaluate(Decimal("50")).applied is False


def test_unknown_total_gets_no_guaranteed_discount():
    # A 'from'/inspection order whose exact total is unknown must NOT get a
    # guaranteed discount amount (spec §8), even if the partial figure is > 100.
    r = discount.evaluate(Decimal("500"), total_is_known=False)
    assert r.applied is False and r.reason == "unknown_total"
    assert r.discount_amount == Decimal("0.00")
    assert r.final_total == Decimal("500.00")


def test_recompute_is_idempotent_never_stacks():
    # Applied exactly once: recomputing the SAME subtotal yields the SAME result,
    # never compounding (spec §9 — duplicate webhook / reopen / summary regen).
    first = discount.evaluate(Decimal("120"))
    again = discount.evaluate(Decimal(str(first.eligible_subtotal)))  # re-eval on subtotal
    assert again.discount_amount == Decimal("18.00")
    assert again.final_total == Decimal("102.00")


# --- Quote-engine integration (spec §6 order of operations) ------------------
def test_multi_item_order_over_100_discounts_to_88_40():
    # spec §7: 5×Shirt@9 (45) + 5×Trousers@11 (55) + 1×Hand Towel@4 (4) = 104.
    q = pricing.calculate_estimate([
        {"item_code": "CLEAN_PRESS_SHIRT", "quantity": 5},
        {"item_code": "CLEAN_PRESS_TROUSERS", "quantity": 5},
        {"item_code": "CLEAN_PRESS_HAND_TOWEL", "quantity": 1},
    ])
    assert q.eligible_subtotal == 104.0
    assert q.discount_applied is True
    assert q.discount_amount == 15.60
    assert q.customer_total == 88.40
    assert q.discount_percentage == 15.0
    assert q.discount_rule_code == "ORDER_OVER_100_DISCOUNT"


def test_order_exactly_100_gets_no_discount():
    # 5×Shirt@9 (45) + 5×Trousers@11 (55) = 100 exactly -> no discount.
    q = pricing.calculate_estimate([
        {"item_code": "CLEAN_PRESS_SHIRT", "quantity": 5},
        {"item_code": "CLEAN_PRESS_TROUSERS", "quantity": 5},
    ])
    assert q.eligible_subtotal == 100.0
    assert q.discount_applied is False
    assert q.customer_total == 100.0


def test_editing_quantity_recalculates_eligibility():
    # Adding an item crosses the threshold; removing it drops back below.
    below = pricing.calculate_estimate([{"item_code": "CLEAN_PRESS_SHIRT", "quantity": 5},
                                        {"item_code": "CLEAN_PRESS_TROUSERS", "quantity": 5}])
    assert below.discount_applied is False and below.customer_total == 100.0
    above = pricing.calculate_estimate([{"item_code": "CLEAN_PRESS_SHIRT", "quantity": 6},
                                        {"item_code": "CLEAN_PRESS_TROUSERS", "quantity": 5}])
    assert above.eligible_subtotal == 109.0
    assert above.discount_applied is True
    assert above.customer_total == round(109.0 * 0.85, 2)   # 92.65


def test_starting_price_order_has_no_guaranteed_discount():
    # 2 pairs of sneakers 'from 50' = pending -> exact total unknown -> no
    # guaranteed discount even though 2×50 would exceed 100 (spec §8).
    q = pricing.calculate_estimate([{"item_code": "SHOE_CARE_SPORTS_SNEAKERS", "quantity": 2}])
    assert q.is_final is False
    assert q.discount_applied is False
    assert q.discount_reason == "unknown_total"
    assert q.discount_amount == 0.0


# --- Customer-facing summary (spec §10) -------------------------------------
def test_summary_shows_discount_block_and_no_vat():
    q = pricing.calculate_estimate([
        {"item_code": "CLEAN_PRESS_SHIRT", "quantity": 5},
        {"item_code": "CLEAN_PRESS_TROUSERS", "quantity": 5},
        {"item_code": "CLEAN_PRESS_HAND_TOWEL", "quantity": 1},
    ])
    summary = pricing.format_quote_summary(q)
    assert "Subtotal — AED 104" in summary
    assert "Automatic 15% discount — AED 15.60 off" in summary
    assert "Final price — AED 88.40" in summary
    for banned in ("VAT", "vat", "tax", "excl", "incl"):
        assert banned not in summary


def test_below_threshold_summary_has_no_discount_line():
    q = pricing.calculate_estimate([{"item_code": "CLEAN_PRESS_SHIRT", "quantity": 3}])  # 27
    summary = pricing.format_quote_summary(q)
    assert "discount" not in summary.lower()
    assert "Subtotal" not in summary          # no zero-value discount shown (spec §10)
    assert "Final price — AED 27" in summary


# --- FSM PATCH + order-row surfacing (spec §§11/13/29) ----------------------
def test_booking_pricing_updates_carry_discount_snapshot():
    from services import booking_flow as bf
    updates = bf._pricing_updates(
        [{"item_code": "CLEAN_PRESS_SHIRT", "quantity": 5},
         {"item_code": "CLEAN_PRESS_TROUSERS", "quantity": 5},
         {"item_code": "CLEAN_PRESS_HAND_TOWEL", "quantity": 1}],
        "CLEAN_PRESS", "Clean & Press")
    assert updates["eligible_subtotal"] == 104.0
    assert updates["discount_amount"] == 15.60
    assert updates["discount_rule_code"] == "ORDER_OVER_100_DISCOUNT"
    assert updates["estimated_total"] == 88.40    # final the customer pays / Stripe charges
    assert updates["amount"] == 88.40


def test_order_row_pricing_block_surfaces_discount():
    from db.repositories import orders_repo
    row = {"id": "x", "order_id": "LK-2026-000009", "status": "pickup_scheduled",
           "line_items": [{"item_code": "CLEAN_PRESS_SHIRT", "line_kind": "exact"}],
           "eligible_subtotal": 104.0, "discount_amount": 15.60,
           "discount_percentage": 15.0, "discount_threshold": 100.0,
           "discount_rule_code": "ORDER_OVER_100_DISCOUNT",
           "subtotal_amount": 84.19, "vat_amount": 4.21,
           "estimated_total": 88.40, "amount": 88.40, "vat_rate": 0.05}
    read = orders_repo.to_read(row)
    p = read["pricing"]
    assert p["final_price"] == 88.40                 # dashboard shows the discounted total
    assert p["discount_applied"] is True
    assert p["discount_amount"] == 15.60
    assert p["discount_percentage"] == 15.0
    assert p["eligible_subtotal"] == 104.0


def test_order_row_below_threshold_hides_discount():
    from db.repositories import orders_repo
    row = {"id": "y", "order_id": "LK-2026-000010", "status": "pickup_scheduled",
           "line_items": [{"item_code": "CLEAN_PRESS_SHIRT", "line_kind": "exact"}],
           "discount_amount": 0.0, "estimated_total": 27.0, "amount": 27.0, "vat_rate": 0.05}
    p = orders_repo.to_read(row)["pricing"]
    assert p["final_price"] == 27.0
    assert p["discount_applied"] is False
    assert p["discount_amount"] is None


# --- Snapshot (spec §11) -----------------------------------------------------
def test_discount_snapshot_fields():
    r = discount.evaluate(Decimal("120"))
    snap = r.to_snapshot()
    assert snap["discount_rule_code"] == "ORDER_OVER_100_DISCOUNT"
    assert snap["discount_threshold"] == 100.0
    assert snap["discount_percentage"] == 15.0
    assert snap["discount_amount"] == 18.0
    assert snap["eligible_subtotal"] == 120.0
    assert snap["final_total"] == 102.0
