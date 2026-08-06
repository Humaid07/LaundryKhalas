"""Routing simulator override application (Area E)."""
from datetime import datetime

import pytest

from services.routing import simulator
from services.routing import candidate_loader

T = datetime(2026, 8, 6, 12, 30)


def _cands():
    return [{
        "id": "F1", "code": "TEST_A", "name": "A", "is_test_facility": True,
        "operating_status": "open", "is_active": True, "accepts_orders": True,
        "latitude": 25.1, "longitude": 55.2, "service_radius_km": 12,
        "service_codes": {"WASH_AND_FOLD"}, "express_service_codes": set(), "capabilities": set(),
        "rating": 4.5, "review_count": 50, "quality_score": 85, "supports_express": False,
        "turnaround_hours": 48, "max_concurrent_orders": 20, "active_load": 0,
        "current_workload_pct": None, "market": None, "timings": {},
        "drivers": [{"id": "d1", "driver_code": "TEST_A_D1", "active": True, "status": "free",
                     "employment_status": "active", "shift_start": "08:00", "shift_end": "16:00",
                     "express_eligible": False, "max_concurrent_assignments": 1,
                     "active_assignment_count": 0}],
    }]


def test_facility_status_override_does_not_mutate_original():
    original = _cands()
    patched = simulator.apply_overrides(original, {"facilities": {"TEST_A": {"operating_status": "closed"}}})
    assert patched[0]["operating_status"] == "closed"
    assert original[0]["operating_status"] == "open"  # deep-copied, no mutation


def test_driver_offline_override():
    patched = simulator.apply_overrides(_cands(), {"drivers": {"TEST_A_D1": {"status": "offline"}}})
    assert patched[0]["drivers"][0]["status"] == "offline"


def test_remove_service_override():
    patched = simulator.apply_overrides(_cands(), {"facilities": {"TEST_A": {"remove_services": ["WASH_AND_FOLD"]}}})
    assert "WASH_AND_FOLD" not in patched[0]["service_codes"]


def test_rating_override():
    patched = simulator.apply_overrides(_cands(), {"facilities": {"TEST_A": {"rating": 3.0, "review_count": 200}}})
    assert patched[0]["rating"] == 3.0 and patched[0]["review_count"] == 200


async def test_simulate_reflects_override_without_writes(monkeypatch):
    async def fake_load(*, is_test, market=None):
        return _cands()

    monkeypatch.setattr(candidate_loader, "load_candidates", fake_load)
    req = {"service_code": "WASH_AND_FOLD", "lat": 25.1, "lon": 55.2, "priority": "standard",
           "is_test": True, "required_capabilities": []}

    base = await simulator.simulate(req, when=T)
    assert base["selected_facility_id"] == "F1"

    # simulate the only driver going offline -> no eligible facility.
    off = await simulator.simulate(req, when=T, overrides={"drivers": {"TEST_A_D1": {"status": "offline"}}})
    assert off["selected_facility_id"] is None
    assert off["eligible_count"] == 0
