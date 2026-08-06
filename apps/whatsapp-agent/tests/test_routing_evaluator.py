"""Shared routing evaluator — the ~55-scenario matrix at the pure level (Area B)."""
from datetime import datetime

from services.routing import evaluator

T = datetime(2026, 8, 6, 12, 30)          # DEFAULT_SEED_TIME (Thu 12:30)
DAY = (T.weekday() + 1) % 7               # mapped day for timings


def drv(did="d1", **over):
    base = {"id": did, "active": True, "status": "free", "employment_status": "active",
            "shift_start": "08:00", "shift_end": "16:00", "express_eligible": False,
            "max_concurrent_assignments": 1, "active_assignment_count": 0}
    base.update(over)
    return base


def fac(fid="F1", **over):
    base = {
        "id": fid, "code": fid, "name": fid, "is_test_facility": True, "environment": "TEST",
        "operating_status": "open", "is_active": True, "accepts_orders": True,
        "latitude": 25.10, "longitude": 55.20, "service_radius_km": 12,
        "service_codes": {"WASH_AND_FOLD"}, "express_service_codes": set(),
        "capabilities": set(), "rating": 4.5, "review_count": 50, "quality_score": 85,
        "supports_express": False, "turnaround_hours": 48, "max_concurrent_orders": 20,
        "active_load": 0, "current_workload_pct": None, "market": None,
        "timings": {}, "drivers": [drv()],
    }
    base.update(over)
    return base


def req(**over):
    base = {"service_code": "WASH_AND_FOLD", "lat": 25.10, "lon": 55.20,
            "priority": "standard", "is_test": True, "required_capabilities": []}
    base.update(over)
    return base


def _by_id(rows):
    return {r["facility_id"]: r for r in rows}


# ============================ service eligibility ========================
def test_highest_rated_without_service_is_rejected():
    a = fac("A", rating=4.9, service_codes={"SHOES"})
    b = fac("B", rating=4.0, service_codes={"WASH_AND_FOLD"})
    res = evaluator.evaluate([a, b], req(), T)
    rej = _by_id(res["rejected_candidates"])
    assert "SERVICE_NOT_SUPPORTED" in rej["A"]["rejection_reasons"]
    assert res["selected_facility_id"] == "B"


def test_specialist_capability_required():
    a = fac("A", capabilities=set())
    b = fac("B", capabilities={"LEATHER"})
    res = evaluator.evaluate([a, b], req(required_capabilities=["LEATHER"]), T)
    rej = _by_id(res["rejected_candidates"])
    assert "SPECIALIST_CAPABILITY_MISSING" in rej["A"]["rejection_reasons"]
    assert res["selected_facility_id"] == "B"


def test_shoe_clean_but_not_restoration():
    a = fac("A", service_codes={"SHOES"}, capabilities={"SHOE_CLEAN"})
    res = evaluator.evaluate([a], req(service_code="SHOES", required_capabilities=["SHOE_RESTORATION"]), T)
    assert res["selected_facility_id"] is None
    assert "SPECIALIST_CAPABILITY_MISSING" in res["rejected_candidates"][0]["rejection_reasons"]


# ============================ ratings & reviews ==========================
def test_weighted_review_beats_raw_rating():
    # 4.9 with 3 reviews vs 4.7 with 160 reviews; else equal -> weighted picks 4.7.
    a = fac("A", rating=4.9, review_count=3)
    b = fac("B", rating=4.7, review_count=160)
    res = evaluator.evaluate([a, b], req(), T)
    assert res["selected_facility_id"] == "B"


def test_higher_rating_wins_when_else_equal():
    a = fac("A", rating=4.8, review_count=100)
    b = fac("B", rating=4.3, review_count=100)
    res = evaluator.evaluate([a, b], req(), T)
    assert res["selected_facility_id"] == "A"


# ============================ driver availability ========================
def test_one_available_beats_three_unavailable():
    a = fac("A", drivers=[drv("a1")])  # 1 available
    b = fac("B", drivers=[drv("b1", status="offline"),
                          drv("b2", status="on_leave"),
                          drv("b3", active_assignment_count=1)])  # 3 total, 0 available
    res = evaluator.evaluate([a, b], req(), T)
    assert res["selected_facility_id"] == "A"
    rej = _by_id(res["rejected_candidates"])
    assert rej["B"]["total_drivers"] == 3 and rej["B"]["drivers_available"] == 0
    assert "NO_AVAILABLE_DRIVER" in rej["B"]["rejection_reasons"]


def test_three_total_one_scheduled_counts_one_available():
    a = fac("A", drivers=[drv("a1"), drv("a2", shift_start="14:00", shift_end="22:00"),
                          drv("a3", shift_start="15:00", shift_end="23:00")])
    res = evaluator.evaluate([a], req(), T)
    row = res["eligible_candidates"][0]
    assert row["total_drivers"] == 3 and row["drivers_available"] == 1


def test_one_on_break_one_available_stays_eligible():
    a = fac("A", drivers=[drv("a1", status="on_break", break_start="12:00", break_end="13:00"),
                          drv("a2")])
    res = evaluator.evaluate([a], req(), T)
    assert res["selected_facility_id"] == "A"


def test_single_driver_on_break_no_pickup():
    a = fac("A", drivers=[drv("a1", break_start="12:00", break_end="13:00")])
    res = evaluator.evaluate([a], req(), T)
    assert res["selected_facility_id"] is None
    assert "DRIVER_ON_BREAK" in res["rejected_candidates"][0]["rejection_reasons"]


# ============================ working hours ==============================
def test_facility_closed_rejected():
    a = fac("A", timings={DAY: {"is_closed": True}})
    res = evaluator.evaluate([a], req(), T)
    assert "FACILITY_OUTSIDE_WORKING_HOURS" in res["rejected_candidates"][0]["rejection_reasons"]


def test_all_drivers_outside_shift_no_pickup():
    a = fac("A", drivers=[drv("a1", shift_start="15:00", shift_end="22:00")])  # not yet on shift at 12:30
    res = evaluator.evaluate([a], req(), T)
    assert res["selected_facility_id"] is None
    reasons = res["rejected_candidates"][0]["rejection_reasons"]
    assert "NO_DRIVERS_SCHEDULED" in reasons and "DRIVER_OUTSIDE_SHIFT" in reasons


# ============================ capacity / status ==========================
def test_full_capacity_rejected():
    a = fac("A", current_workload_pct=100)
    res = evaluator.evaluate([a], req(), T)
    assert "CAPACITY_UNAVAILABLE" in res["rejected_candidates"][0]["rejection_reasons"]


def test_paused_and_closed_rejected_immediately():
    p = evaluator.evaluate([fac("P", operating_status="paused")], req(), T)
    assert "FACILITY_PAUSED" in p["rejected_candidates"][0]["rejection_reasons"]
    c = evaluator.evaluate([fac("C", operating_status="closed")], req(), T)
    assert "FACILITY_CLOSED" in c["rejected_candidates"][0]["rejection_reasons"]


# ============================ express ====================================
def test_express_needs_support_and_express_driver():
    a = fac("A", supports_express=True, express_service_codes={"WASH_AND_FOLD"},
            drivers=[drv("a1", express_eligible=True)])
    res = evaluator.evaluate([a], req(priority="express"), T)
    assert res["selected_facility_id"] == "A"
    assert res["eligible_candidates"][0]["earliest_pickup_slot"]["express"] is True


def test_express_supported_but_driver_not_express():
    a = fac("A", supports_express=True, express_service_codes={"WASH_AND_FOLD"},
            drivers=[drv("a1", express_eligible=False)])
    res = evaluator.evaluate([a], req(priority="express"), T)
    assert res["selected_facility_id"] is None
    assert "NO_EXPRESS_DRIVER_AVAILABLE" in res["rejected_candidates"][0]["rejection_reasons"]


def test_express_not_supported():
    a = fac("A", supports_express=False, drivers=[drv("a1", express_eligible=True)])
    res = evaluator.evaluate([a], req(priority="express"), T)
    assert "EXPRESS_NOT_SUPPORTED" in res["rejected_candidates"][0]["rejection_reasons"]


def test_express_after_cutoff_no_same_day_slot():
    late = datetime(2026, 8, 6, 16, 0)  # after 3 PM cutoff
    a = fac("A", supports_express=True, express_service_codes={"WASH_AND_FOLD"},
            timings={DAY: {"opens_at": "08:00", "closes_at": "22:00"}},
            drivers=[drv("a1", express_eligible=True, shift_start="08:00", shift_end="22:00")])
    res = evaluator.evaluate([a], req(priority="express"), late)
    # standard drivers exist, but no SAME-DAY express slot is auto-confirmed.
    if res["selected_facility_id"] == "A":
        slot = res["eligible_candidates"][0]["earliest_pickup_slot"]
        assert slot["start"][:10] != "2026-08-06"  # deferred to a later day
    else:
        assert "NO_EXPRESS_DRIVER_AVAILABLE" in res["rejected_candidates"][0]["rejection_reasons"]


# ============================ distance vs rating =========================
def test_closer_available_beats_farther_when_only_driver_unavailable():
    near = fac("NEAR", rating=4.1, latitude=25.10, longitude=55.20, drivers=[drv("n1")])
    far = fac("FAR", rating=4.8, latitude=25.20, longitude=55.30,
              drivers=[drv("f1", status="offline")])  # its only driver unavailable
    res = evaluator.evaluate([near, far], req(), T)
    assert res["selected_facility_id"] == "NEAR"


# ============================ no eligible facility =======================
def test_no_eligible_routes_to_manual():
    a = fac("A", operating_status="paused")
    res = evaluator.evaluate([a], req(), T)
    assert res["selected_facility_id"] is None
    assert "manual" in res["selection_reason"].lower()
    assert res["eligible_count"] == 0


# ============================ explanation completeness ===================
def test_breakdown_exposes_availability_and_scores():
    a = fac("A")
    res = evaluator.evaluate([a], req(), T)
    row = res["eligible_candidates"][0]
    for k in ("total_drivers", "drivers_available", "drivers_on_break", "drivers_on_leave",
              "drivers_assigned", "drivers_outside_shift", "express_drivers_available",
              "earliest_pickup_slot", "score", "score_components", "weighted_rating",
              "distance_km", "remaining_capacity", "rejection_reasons"):
        assert k in row
    assert res["selected_pickup_slot_id"] and res["selected_driver_id"]
