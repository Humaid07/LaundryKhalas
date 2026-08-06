"""The 11 trial (TEST) facilities + their drivers — the single source of truth.

Pure data (no DB) so it is unit-testable and consumed by both the idempotent seed
command and the acceptance tests. Every facility/driver here is TEST-only
(is_test_facility / is_test_driver); production routing never sees them.

DEFAULT_SEED_TIME = 2026-08-06 (Thu) 12:30 Asia/Dubai. The spec's per-driver seed
statuses cannot all hold at one instant (see the design doc); drivers store real
shift/break/leave data and the availability engine derives status at any time. At
12:30 every stated status holds, EXCEPT the two later-shift "available" drivers
(TEST_BAR1_DRIVER_02, TEST_PALM_DRIVER_03) whose shifts are set to 12:00-20:00
(documented deviation from the literal 14:00 start) to realise the intended
"two overlapping shifts, both available" at seed time.
"""
from __future__ import annotations

from datetime import datetime

DEFAULT_SEED_TIME = datetime(2026, 8, 6, 12, 30)  # Thu 12:30


def _all_days(o, c):
    return {d: (o, c) for d in range(7)}


def _mon_sat_sun(o1, c1, o2, c2):
    # Mon-Sat = mapped days 1..6; Sun = 0.
    h = {d: (o1, c1) for d in range(1, 7)}
    h[0] = (o2, c2)
    return h


def _mon_sat_closed(o, c):
    return {d: (o, c) for d in range(1, 7)}  # Sun (0) absent = closed


# service code constants (match the spec's service names)
WF, CP, PO = "WASH_AND_FOLD", "CLEAN_AND_PRESS", "PRESS_ONLY"
BED, TRAD, SUIT = "BEDDING_AND_HOME_TEXTILES", "TRADITIONAL_WEAR", "SUITS_AND_BLAZERS"
SHOES, BAGS, LEATHER = "SHOES", "BAGS_AND_ACCESSORIES", "LEATHER"
WED, REST = "WEDDING_AND_EVENING_DRESSES", "RESTORATION"
CURT, CARP = "CURTAINS", "CARPETS_AND_RUGS"
ALT, TOYS, SOFA = "ALTERATIONS_AND_GARMENT_REPAIR", "TOYS_AND_MASCOTS", "SOFA_AND_UPHOLSTERY"


TRIAL_FACILITIES: list[dict] = [
    {
        "code": "TEST_BAR1_001", "name": "TEST Barsha One Laundry", "area": "Al Barsha 1",
        "latitude": 25.1120, "longitude": 55.1960, "rating": 4.1, "review_count": 48,
        "quality_score": 82, "operating_status": "open", "service_radius_km": 7,
        "capacity_level": "MEDIUM", "max_concurrent_orders": 20, "current_workload_pct": 35,
        "supports_express": True, "turnaround_hours": 48, "hours": _all_days("08:00", "22:00"),
        "services": {WF, CP, PO, BED, TRAD, SUIT}, "express_services": {WF, CP, PO},
        "capabilities": set(),
        "drivers": [
            {"code": "TEST_BAR1_DRIVER_01", "name": "TEST Driver Barsha 01",
             "shift_start": "08:00", "shift_end": "16:00", "status": "free", "express_eligible": True},
            # spec shift 14:00-22:00 AVAILABLE -> set to 12:00-20:00 (documented) so available at 12:30
            {"code": "TEST_BAR1_DRIVER_02", "name": "TEST Driver Barsha 02",
             "shift_start": "12:00", "shift_end": "20:00", "status": "free", "express_eligible": False},
        ],
    },
    {
        "code": "TEST_BAR1_002", "name": "TEST Barsha Elite Care", "area": "Al Barsha 1",
        "latitude": 25.1135, "longitude": 55.1985, "rating": 4.8, "review_count": 132,
        "quality_score": 95, "operating_status": "open", "service_radius_km": 9,
        "capacity_level": "LOW", "max_concurrent_orders": 8, "current_workload_pct": 70,
        "supports_express": True, "turnaround_hours": 72, "hours": _mon_sat_sun("10:00", "20:00", "12:00", "18:00"),
        "services": {CP, PO, SHOES, BAGS, LEATHER, WED, REST, TRAD}, "express_services": {CP},
        "capabilities": {"DESIGNER_SHOES", "DESIGNER_BAGS", "LEATHER", "WEDDING_DRESSES",
                         "LUXURY_ITEMS", "RESTORATION"},
        "drivers": [
            {"code": "TEST_BAR1_DRIVER_03", "name": "TEST Driver Barsha 03",
             "shift_start": "12:00", "shift_end": "20:00", "break_start": "16:00", "break_end": "16:30",
             "status": "free", "express_eligible": True},
        ],
    },
    {
        "code": "TEST_DEIRA_001", "name": "TEST Deira Quick Wash", "area": "Deira",
        "latitude": 25.2710, "longitude": 55.3120, "rating": 3.8, "review_count": 75,
        "quality_score": 74, "operating_status": "open", "service_radius_km": 6,
        "capacity_level": "HIGH", "max_concurrent_orders": 35, "current_workload_pct": 20,
        "supports_express": True, "turnaround_hours": 48, "hours": _all_days("07:00", "23:00"),
        "services": {WF, CP, PO, BED, TRAD}, "express_services": {WF, CP, PO}, "capabilities": set(),
        "drivers": [
            {"code": "TEST_DEIRA_DRIVER_01", "name": "TEST Driver Deira 01",
             "shift_start": "07:00", "shift_end": "15:00", "status": "free", "express_eligible": True},
            {"code": "TEST_DEIRA_DRIVER_02", "name": "TEST Driver Deira 02",
             "shift_start": "10:00", "shift_end": "18:00", "status": "assigned", "express_eligible": True},
            {"code": "TEST_DEIRA_DRIVER_03", "name": "TEST Driver Deira 03",
             "shift_start": "15:00", "shift_end": "23:00", "status": "free", "express_eligible": False},
        ],
    },
    {
        "code": "TEST_DEIRA_002", "name": "TEST Deira Premium Laundry", "area": "Deira",
        "latitude": 25.2685, "longitude": 55.3155, "rating": 4.7, "review_count": 160,
        "quality_score": 93, "operating_status": "busy", "service_radius_km": 8,
        "capacity_level": "MEDIUM", "max_concurrent_orders": 18, "current_workload_pct": 90,
        "supports_express": True, "turnaround_hours": 48, "hours": _mon_sat_sun("09:00", "21:00", "10:00", "19:00"),
        "services": {WF, CP, PO, BED, CURT, CARP, SUIT}, "express_services": {PO},
        "capabilities": {"CURTAIN_MEASUREMENT", "CARPET_MEASUREMENT"},
        "drivers": [
            {"code": "TEST_DEIRA_DRIVER_04", "name": "TEST Driver Deira 04",
             "shift_start": "09:00", "shift_end": "18:00", "status": "assigned", "express_eligible": True},
        ],
    },
    {
        "code": "TEST_DEIRA_003", "name": "TEST Deira Specialist Care", "area": "Deira",
        "latitude": 25.2730, "longitude": 55.3095, "rating": 4.5, "review_count": 88,
        "quality_score": 90, "operating_status": "open", "service_radius_km": 10,
        "capacity_level": "LOW", "max_concurrent_orders": 10, "current_workload_pct": 45,
        "supports_express": False, "turnaround_hours": 96, "hours": _mon_sat_closed("10:00", "20:00"),
        "services": {SHOES, BAGS, LEATHER, REST, ALT, TOYS, WED}, "express_services": set(),
        "capabilities": {"SHOE_REPAIR", "BAG_REPAIR", "LEATHER_RESTORATION", "GARMENT_REPAIR",
                         "COMPLEX_ALTERATIONS", "LARGE_TOY_HANDLING", "WEDDING_DRESS_INSPECTION"},
        "drivers": [
            {"code": "TEST_DEIRA_DRIVER_05", "name": "TEST Driver Deira 05",
             "shift_start": "10:00", "shift_end": "18:00", "status": "free", "express_eligible": False},
            {"code": "TEST_DEIRA_DRIVER_06", "name": "TEST Driver Deira 06",
             "shift_start": "12:00", "shift_end": "20:00", "break_start": "12:00", "break_end": "13:00",
             "status": "free", "express_eligible": False},
        ],
    },
    {
        "code": "TEST_BAR2_001", "name": "TEST Barsha Two Cleaners", "area": "Al Barsha 2",
        "latitude": 25.0995, "longitude": 55.2050, "rating": 4.3, "review_count": 104,
        "quality_score": 86, "operating_status": "open", "service_radius_km": 8,
        "capacity_level": "HIGH", "max_concurrent_orders": 30, "current_workload_pct": 40,
        "supports_express": True, "turnaround_hours": 48, "hours": _all_days("08:00", "22:00"),
        "services": {WF, CP, PO, BED, CURT, CARP, SOFA, ALT}, "express_services": {WF, CP, PO},
        "capabilities": {"STANDARD_ALTERATIONS", "CURTAIN_CLEANING", "CARPET_CLEANING",
                         "REMOVABLE_SOFA_COVERS"},
        "drivers": [
            {"code": "TEST_BAR2_DRIVER_01", "name": "TEST Driver Barsha2 01",
             "shift_start": "08:00", "shift_end": "16:00", "status": "free", "express_eligible": True},
            {"code": "TEST_BAR2_DRIVER_02", "name": "TEST Driver Barsha2 02",
             "shift_start": "11:00", "shift_end": "19:00", "status": "free", "express_eligible": True},
            {"code": "TEST_BAR2_DRIVER_03", "name": "TEST Driver Barsha2 03",
             "shift_start": "14:00", "shift_end": "22:00", "status": "offline", "express_eligible": False},
        ],
    },
    {
        "code": "TEST_MARINA_001", "name": "TEST Marina Express Laundry", "area": "Dubai Marina",
        "latitude": 25.0780, "longitude": 55.1400, "rating": 4.6, "review_count": 145,
        "quality_score": 91, "operating_status": "open", "service_radius_km": 6,
        "capacity_level": "MEDIUM", "max_concurrent_orders": 22, "current_workload_pct": 30,
        "supports_express": True, "turnaround_hours": 24, "hours": _all_days("07:00", "23:00"),
        "services": {WF, CP, PO, BED, SUIT, TRAD}, "express_services": {WF, CP, PO},
        "capabilities": {"SAME_DAY_PROCESSING"},
        "drivers": [
            {"code": "TEST_MARINA_DRIVER_01", "name": "TEST Driver Marina 01",
             "shift_start": "07:00", "shift_end": "15:00", "status": "free", "express_eligible": True},
            {"code": "TEST_MARINA_DRIVER_02", "name": "TEST Driver Marina 02",
             "shift_start": "15:00", "shift_end": "23:00", "status": "free", "express_eligible": True},
        ],
    },
    {
        "code": "TEST_JVC_001", "name": "TEST JVC Daily Laundry", "area": "Jumeirah Village Circle",
        "latitude": 25.0585, "longitude": 55.2090, "rating": 4.0, "review_count": 69,
        "quality_score": 80, "operating_status": "open", "service_radius_km": 7,
        "capacity_level": "HIGH", "max_concurrent_orders": 35, "current_workload_pct": 25,
        "supports_express": True, "turnaround_hours": 48, "hours": _all_days("08:00", "22:00"),
        "services": {WF, CP, PO, BED, TRAD, SUIT}, "express_services": {WF, CP, PO}, "capabilities": set(),
        "drivers": [
            {"code": "TEST_JVC_DRIVER_01", "name": "TEST Driver JVC 01",
             "shift_start": "08:00", "shift_end": "16:00", "status": "free", "express_eligible": True},
            {"code": "TEST_JVC_DRIVER_02", "name": "TEST Driver JVC 02",
             "shift_start": "10:00", "shift_end": "18:00", "status": "free", "express_eligible": True},
            {"code": "TEST_JVC_DRIVER_03", "name": "TEST Driver JVC 03",
             "shift_start": "14:00", "shift_end": "22:00", "status": "on_leave", "express_eligible": False},
        ],
    },
    {
        "code": "TEST_JVC_002", "name": "TEST JVC Specialist Cleaners", "area": "Jumeirah Village Circle",
        "latitude": 25.0560, "longitude": 55.2115, "rating": 4.9, "review_count": 117,
        "quality_score": 97, "operating_status": "open", "service_radius_km": 9,
        "capacity_level": "LOW", "max_concurrent_orders": 7, "current_workload_pct": 65,
        "supports_express": False, "turnaround_hours": 96, "hours": _mon_sat_closed("10:00", "19:00"),
        "services": {SHOES, BAGS, LEATHER, REST, WED, ALT, SOFA}, "express_services": set(),
        "capabilities": {"DESIGNER_SHOES", "DESIGNER_BAGS", "LEATHER", "WEDDING_DRESSES",
                         "RESTORATION", "COMPLEX_ALTERATIONS", "IN_PLACE_SOFA_CLEANING",
                         "DESIGNER_SHOE_RESTORATION"},
        "drivers": [
            {"code": "TEST_JVC_DRIVER_04", "name": "TEST Driver JVC 04",
             "shift_start": "10:00", "shift_end": "19:00", "break_start": "14:00", "break_end": "15:00",
             "status": "free", "express_eligible": False},
        ],
    },
    {
        "code": "TEST_PALM_001", "name": "TEST Palm Luxury Care", "area": "Palm Jumeirah",
        "latitude": 25.1130, "longitude": 55.1385, "rating": 4.9, "review_count": 180,
        "quality_score": 98, "operating_status": "open", "service_radius_km": 8,
        "capacity_level": "LOW", "max_concurrent_orders": 8, "current_workload_pct": 55,
        "supports_express": True, "turnaround_hours": 72, "hours": _mon_sat_sun("10:00", "20:00", "12:00", "18:00"),
        # Express CLEAN_AND_PRESS implies CP is offered (spec listed express-CP but
        # omitted CP from services); CP added so express ⊆ services holds.
        "services": {SHOES, BAGS, LEATHER, REST, WED, SUIT, TRAD, CP}, "express_services": {CP},
        "capabilities": {"LUXURY_ITEMS", "WEDDING_DRESSES", "LEATHER_RESTORATION",
                         "DESIGNER_SHOE_RESTORATION", "DESIGNER_BAG_RESTORATION"},
        "drivers": [
            {"code": "TEST_PALM_DRIVER_01", "name": "TEST Driver Palm 01",
             "shift_start": "12:00", "shift_end": "20:00", "status": "free", "express_eligible": True},
        ],
    },
    {
        "code": "TEST_PALM_002", "name": "TEST Palm Everyday Laundry", "area": "Palm Jumeirah",
        "latitude": 25.1105, "longitude": 55.1420, "rating": 4.2, "review_count": 96,
        "quality_score": 84, "operating_status": "open", "service_radius_km": 6,
        "capacity_level": "HIGH", "max_concurrent_orders": 28, "current_workload_pct": 30,
        "supports_express": True, "turnaround_hours": 48, "hours": _all_days("08:00", "22:00"),
        "services": {WF, CP, PO, BED, CURT, TRAD}, "express_services": {WF, CP, PO},
        "capabilities": {"STANDARD_CURTAIN_CLEANING"},
        "drivers": [
            {"code": "TEST_PALM_DRIVER_02", "name": "TEST Driver Palm 02",
             "shift_start": "08:00", "shift_end": "16:00", "status": "free", "express_eligible": True},
            # spec shift 14:00-22:00 AVAILABLE -> set to 12:00-20:00 (documented) so available at 12:30
            {"code": "TEST_PALM_DRIVER_03", "name": "TEST Driver Palm 03",
             "shift_start": "12:00", "shift_end": "20:00", "status": "free", "express_eligible": False},
        ],
    },
]


def total_driver_count() -> int:
    return sum(len(f["drivers"]) for f in TRIAL_FACILITIES)
