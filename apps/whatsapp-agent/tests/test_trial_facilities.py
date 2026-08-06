"""Acceptance tests for the 11 trial facilities + drivers (Area D)."""
from services.routing import availability as av
from services.routing.trial_facilities import TRIAL_FACILITIES, DEFAULT_SEED_TIME, total_driver_count

EXPECTED_CODES = {
    "TEST_BAR1_001", "TEST_BAR1_002", "TEST_DEIRA_001", "TEST_DEIRA_002", "TEST_DEIRA_003",
    "TEST_BAR2_001", "TEST_MARINA_001", "TEST_JVC_001", "TEST_JVC_002", "TEST_PALM_001",
    "TEST_PALM_002",
}


# --------------------------- structural acceptance -----------------------
def test_exactly_11_facilities_with_expected_codes():
    assert len(TRIAL_FACILITIES) == 11
    assert {f["code"] for f in TRIAL_FACILITIES} == EXPECTED_CODES


def test_no_facility_has_more_than_three_drivers():
    assert all(1 <= len(f["drivers"]) <= 3 for f in TRIAL_FACILITIES)


def test_driver_count_distribution_has_1_2_and_3():
    counts = sorted(len(f["drivers"]) for f in TRIAL_FACILITIES)
    assert 1 in counts and 2 in counts and 3 in counts


def test_area_distribution_matches_spec():
    from collections import Counter
    by_area = Counter(f["area"] for f in TRIAL_FACILITIES)
    assert by_area["Al Barsha 1"] == 2
    assert by_area["Deira"] == 3
    assert by_area["Al Barsha 2"] == 1
    assert by_area["Dubai Marina"] == 1
    assert by_area["Jumeirah Village Circle"] == 2
    assert by_area["Palm Jumeirah"] == 2


def test_ratings_and_reviews_differ():
    ratings = {f["rating"] for f in TRIAL_FACILITIES}
    reviews = {f["review_count"] for f in TRIAL_FACILITIES}
    assert len(ratings) >= 6 and len(reviews) >= 8


def test_coordinates_are_distinct():
    coords = [(f["latitude"], f["longitude"]) for f in TRIAL_FACILITIES]
    assert len(coords) == len(set(coords))


def test_express_services_subset_of_services():
    for f in TRIAL_FACILITIES:
        assert f["express_services"] <= f["services"], f["code"]


def test_specialists_have_capabilities():
    elite = next(f for f in TRIAL_FACILITIES if f["code"] == "TEST_BAR1_002")
    assert "LEATHER" in elite["capabilities"] and "WEDDING_DRESSES" in elite["capabilities"]
    general = next(f for f in TRIAL_FACILITIES if f["code"] == "TEST_DEIRA_001")
    assert general["capabilities"] == set()


# --------------------- derived seed-time driver statuses -----------------
_EXPECTED_STATUS = {
    "TEST_BAR1_DRIVER_01": av.AVAILABLE, "TEST_BAR1_DRIVER_02": av.AVAILABLE,
    "TEST_BAR1_DRIVER_03": av.AVAILABLE,
    "TEST_DEIRA_DRIVER_01": av.AVAILABLE, "TEST_DEIRA_DRIVER_02": av.ASSIGNED,
    "TEST_DEIRA_DRIVER_03": av.NOT_YET_ON_SHIFT,
    "TEST_DEIRA_DRIVER_04": av.ASSIGNED,
    "TEST_DEIRA_DRIVER_05": av.AVAILABLE, "TEST_DEIRA_DRIVER_06": av.ON_BREAK,
    "TEST_BAR2_DRIVER_01": av.AVAILABLE, "TEST_BAR2_DRIVER_02": av.AVAILABLE,
    "TEST_BAR2_DRIVER_03": av.OFFLINE,
    "TEST_MARINA_DRIVER_01": av.AVAILABLE, "TEST_MARINA_DRIVER_02": av.NOT_YET_ON_SHIFT,
    "TEST_JVC_DRIVER_01": av.AVAILABLE, "TEST_JVC_DRIVER_02": av.AVAILABLE,
    "TEST_JVC_DRIVER_03": av.ON_LEAVE,
    "TEST_JVC_DRIVER_04": av.AVAILABLE,
    "TEST_PALM_DRIVER_01": av.AVAILABLE,
    "TEST_PALM_DRIVER_02": av.AVAILABLE, "TEST_PALM_DRIVER_03": av.AVAILABLE,
}


def test_seed_time_driver_statuses_match_spec():
    for f in TRIAL_FACILITIES:
        for d in f["drivers"]:
            got = av.compute_driver_availability(d, DEFAULT_SEED_TIME)["status"]
            assert got == _EXPECTED_STATUS[d["code"]], f"{d['code']}: {got}"


def test_total_vs_available_at_seed_time():
    # Deira Quick Wash: 3 total, only 1 available (1 assigned, 1 not-yet-on-shift).
    deira = next(f for f in TRIAL_FACILITIES if f["code"] == "TEST_DEIRA_001")
    avs = [av.compute_driver_availability(d, DEFAULT_SEED_TIME) for d in deira["drivers"]]
    s = av.summarize_drivers(avs)
    assert s["total"] == 3 and s["available"] == 1
    # JVC Daily: 3 total, 2 available (1 on leave).
    jvc = next(f for f in TRIAL_FACILITIES if f["code"] == "TEST_JVC_001")
    s2 = av.summarize_drivers([av.compute_driver_availability(d, DEFAULT_SEED_TIME) for d in jvc["drivers"]])
    assert s2["total"] == 3 and s2["available"] == 2


def test_total_driver_count():
    assert total_driver_count() == 21
