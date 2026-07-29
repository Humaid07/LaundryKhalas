"""Facility-cost engine (founder model 2026-07-29) — pure/offline."""
from __future__ import annotations

from decimal import Decimal

from services import facility_cost as fc


def _line(item, service, ptype, qty=1, measure=None, **flags):
    return {"item_code": item, "service_code": service, "pricing_type": ptype,
            "quantity": qty, "measure": measure, **flags}


def test_standard_per_item_rate_times_count():
    lines = [_line("CLEAN_PRESS_SHIRT", "CLEAN_PRESS", "FIXED_PER_ITEM", qty=5)]
    r = fc.compute_facility_cost(lines, {"CLEAN_PRESS": 4})
    assert r.complete is True
    assert r.facility_cost == Decimal("20.00")     # 4 × 5


def test_measured_per_kg_uses_measure():
    lines = [_line("WASH_FOLD_ADDITIONAL_KG", "WASH_FOLD", "PER_KG", qty=1, measure=6)]
    r = fc.compute_facility_cost(lines, {"WASH_FOLD": 5})
    assert r.facility_cost == Decimal("30.00")     # 5 × 6 kg


def test_per_sqm_uses_measure():
    lines = [_line("HOME_CARE_CARPET_REGULAR_SQM", "HOME_CARE", "PER_SQM", qty=1, measure=10)]
    r = fc.compute_facility_cost(lines, {"HOME_CARE": 8})
    assert r.facility_cost == Decimal("80.00")


def test_minimum_charge_and_operational_fees():
    lines = [_line("CLEAN_PRESS_SHIRT", "CLEAN_PRESS", "FIXED_PER_ITEM", qty=1)]
    r = fc.compute_facility_cost(lines, {"CLEAN_PRESS": 4}, min_charge=15, operational_fees=2)
    assert r.min_charge_applied is True
    assert r.facility_cost == Decimal("17.00")     # max(4,15) + 2


def test_bespoke_line_uses_facility_quotation():
    lines = [_line("BAG_CARE_STANDARD_HANDBAG", "BAG_CARE", "STARTING_FROM", qty=1)]
    r = fc.compute_facility_cost(lines, {}, quotations={"BAG_CARE_STANDARD_HANDBAG": 120})
    assert r.complete is True
    assert r.facility_cost == Decimal("120.00")


def test_incomplete_when_no_rate_or_quote_returns_no_number():
    lines = [_line("BAG_CARE_STANDARD_HANDBAG", "BAG_CARE", "STARTING_FROM", qty=1)]
    r = fc.compute_facility_cost(lines, {})          # no rate, no quotation
    assert r.complete is False
    assert r.facility_cost is None                   # never an arbitrary number
    assert "BAG_CARE_STANDARD_HANDBAG" in r.unpriced_lines


def test_mixed_order_sums_lines():
    lines = [
        _line("CLEAN_PRESS_SHIRT", "CLEAN_PRESS", "FIXED_PER_ITEM", qty=5),   # 4×5 = 20
        _line("WASH_FOLD_ADDITIONAL_KG", "WASH_FOLD", "PER_KG", qty=1, measure=4),  # 5×4 = 20
    ]
    r = fc.compute_facility_cost(lines, {"CLEAN_PRESS": 4, "WASH_FOLD": 5})
    assert r.facility_cost == Decimal("40.00")


def test_snapshot_is_loggable_and_hides_nothing_customer_facing():
    r = fc.compute_facility_cost([_line("X", "CLEAN_PRESS", "FIXED_PER_ITEM", qty=1)],
                                 {"CLEAN_PRESS": 4})
    snap = r.to_snapshot()
    assert snap["kind"] == "facility_cost" and snap["facility_cost"] == 4.0
