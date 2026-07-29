"""Delivery SLA / turnaround + Express eligibility tests (task spec §§23-25/44).

Pure/hermetic — the engine reads config/delivery_sla.json and computes over
catalogue item codes. No DB, no network.
"""
from __future__ import annotations

import datetime as _dt

from services import delivery

# Representative item codes per SLA class.
WASH_FOLD = "WASH_FOLD_6KG"
CLEAN_PRESS = "CLEAN_PRESS_SHIRT"
PRESS_ONLY = "PRESS_ONLY_SHIRT_HANGER"
SHOE = "SHOE_CARE_SPORTS_SNEAKERS"
BAG = "BAG_CARE_STANDARD_HANDBAG"
CARPET = "HOME_CARE_CARPET_REGULAR_SQM"
ALTERATIONS = "ALTERATIONS_GENERAL"
MASCOT = "SOFT_TOY_MASCOT"
TOY = "SOFT_TOY_SMALL"
DRESS = "CLEAN_PRESS_DRESS_NORMAL"
WEDDING = "CLEAN_PRESS_DRESS_EVENING"
SOFA = "HOME_CARE_SOFA_COVER_REGULAR"
DUVET = "HOME_CARE_DUVET"
BLANKET = "HOME_CARE_BLANKET"
BEDDING = "HOME_CARE_MATTRESS_PROTECTOR"


def _hours(item_code):
    t = delivery.order_turnaround([item_code])
    return t["min_hours"], t["max_hours"]


# --- Per-service SLA (task spec §23 list) ------------------------------------
def test_wash_fold_24h():
    assert _hours(WASH_FOLD) == (24, 24)


def test_clean_press_24h():
    assert _hours(CLEAN_PRESS) == (24, 24)


def test_press_only_24h():
    assert _hours(PRESS_ONLY) == (24, 24)


def test_shoe_care_2_3_days():
    assert _hours(SHOE) == (48, 72)


def test_bag_care_2_3_days():
    assert _hours(BAG) == (48, 72)


def test_carpet_2_5_days():
    assert _hours(CARPET) == (48, 120)


def test_alterations_2_days():
    assert _hours(ALTERATIONS) == (48, 48)


def test_mascot_2_days():
    assert _hours(MASCOT) == (48, 48)


def test_toy_cleaning_24h():
    assert _hours(TOY) == (24, 24)


def test_dress_cleaning_24h():
    assert _hours(DRESS) == (24, 24)


def test_wedding_evening_dress_1_2_days():
    assert _hours(WEDDING) == (24, 48)


def test_sofa_cover_24h():
    assert _hours(SOFA) == (24, 24)


def test_bedding_and_covers_24h():
    assert _hours(BEDDING) == (24, 24)


def test_duvets_and_blankets_1_2_days():
    assert _hours(DUVET) == (24, 48)
    assert _hours(BLANKET) == (24, 48)


# --- Express eligibility -----------------------------------------------------
def test_express_only_for_eligible_services():
    for eligible in (WASH_FOLD, CLEAN_PRESS, PRESS_ONLY):
        assert delivery.order_turnaround([eligible])["express_eligible"] is True
    for ineligible in (SHOE, BAG, CARPET, ALTERATIONS, MASCOT, DUVET, SOFA):
        assert delivery.order_turnaround([ineligible])["express_eligible"] is False


def test_express_applies_12h_when_eligible_and_requested():
    t = delivery.order_turnaround([WASH_FOLD], express=True)
    assert t["applied_express"] is True
    assert t["min_hours"] == 12 and t["max_hours"] == 12


def test_express_rejected_for_mixed_order():
    t = delivery.order_turnaround([WASH_FOLD, SHOE], express=True)
    assert t["express_eligible"] is False        # one ineligible item
    assert t["applied_express"] is False
    assert (t["min_hours"], t["max_hours"]) == (48, 72)   # falls back to slowest


# --- Combined order uses the slowest SLA -------------------------------------
def test_combined_order_uses_slowest_sla():
    # Wash & Fold (24h) + Shoe (2-3 days) -> 2-3 days
    t = delivery.order_turnaround([WASH_FOLD, SHOE])
    assert (t["min_hours"], t["max_hours"]) == (48, 72)
    assert t["display_text"] == "2–3 days"
    # + carpet (2-5 days) -> 2-5 days (slowest max_hours wins)
    t2 = delivery.order_turnaround([WASH_FOLD, SHOE, CARPET])
    assert (t2["min_hours"], t2["max_hours"]) == (48, 120)


# --- Delivery estimate off the pickup end time -------------------------------
def test_delivery_estimate_dates_off_pickup():
    pickup_end = _dt.datetime(2026, 7, 24, 18, 0)  # Fri 6 PM
    est = delivery.estimate_delivery([WASH_FOLD], pickup_end)
    assert est["estimated_delivery_start_at"] == pickup_end + _dt.timedelta(hours=24)
    assert est["estimated_delivery_end_at"] == pickup_end + _dt.timedelta(hours=24)
    assert "2026" in est["estimated_delivery_text"]


def test_editing_pickup_time_recalculates_estimate():
    a = delivery.estimate_delivery([WASH_FOLD], _dt.datetime(2026, 7, 24, 18))
    b = delivery.estimate_delivery([WASH_FOLD], _dt.datetime(2026, 7, 25, 18))
    assert a["estimated_delivery_end_at"] != b["estimated_delivery_end_at"]


def test_editing_service_recalculates_sla():
    before = delivery.order_turnaround([WASH_FOLD])
    after = delivery.order_turnaround([SHOE])
    assert before["max_hours"] != after["max_hours"]


def test_no_estimate_dates_without_pickup_time():
    est = delivery.estimate_delivery([SHOE], None)
    assert est["estimated_delivery_end_at"] is None
    assert est["estimated_delivery_text"].startswith("Estimated turnaround")


def test_unknown_item_falls_back_to_safe_default_not_invented():
    t = delivery.order_turnaround(["NOT_A_REAL_ITEM"])
    assert (t["min_hours"], t["max_hours"]) == (24, 48)   # default rule, never fabricated
    assert t["express_eligible"] is False


def test_delivery_options_offers_express_only_when_eligible():
    opts = delivery.delivery_options([WASH_FOLD])
    assert opts["express_eligible"] is True
    assert opts["express"]["hours"] == 12
    assert opts["express"]["surcharge_aed"] is None       # never invented
    opts2 = delivery.delivery_options([SHOE])
    assert opts2["express_eligible"] is False
    assert opts2["express"] is None
