"""Facility eligibility + matching — pure ranking rules + cache invalidation."""
from datetime import datetime

from db import database
from services import facility_matching as fmatch


def _fac(fid, **over):
    base = {
        "id": fid, "code": fid.upper(), "name": fid, "area": "Marina", "city": "Dubai",
        "emirate": "Dubai", "latitude": None, "longitude": None, "service_radius_km": None,
        "capacity_daily": None, "capacity_unit": "orders_per_day", "operating_status": "open",
        "accepts_orders": True, "quality_score": None, "created_at": "2026-01-01",
        "service_codes": {"WASH_FOLD"}, "active_load": 0, "timings": {},
    }
    base.update(over)
    return base


def test_closed_and_paused_excluded():
    facs = [_fac("open"), _fac("closed", operating_status="closed"),
            _fac("paused", operating_status="paused")]
    out = fmatch.rank(facs)
    ids = {f["id"] for f in out}
    assert ids == {"open"}


def test_not_accepting_orders_excluded():
    out = fmatch.rank([_fac("a", accepts_orders=False), _fac("b")])
    assert {f["id"] for f in out} == {"b"}


def test_open_ranks_above_busy():
    out = fmatch.rank([_fac("busy", operating_status="busy"), _fac("open")])
    assert out[0]["id"] == "open"


def test_service_filter_requires_offered_category():
    facs = [_fac("has", service_codes={"WASH_FOLD"}),
            _fac("hasnt", service_codes={"CLEAN_PRESS"})]
    out = fmatch.rank(facs, service_code="WASH_FOLD")
    assert {f["id"] for f in out} == {"has"}


def test_radius_excludes_far_facility():
    near = _fac("near", latitude=25.10, longitude=55.20, service_radius_km=5)
    far = _fac("far", latitude=25.90, longitude=55.90, service_radius_km=5)
    out = fmatch.rank([near, far], lat=25.10, lon=55.20)
    assert {f["id"] for f in out} == {"near"}
    assert out[0]["distance_km"] == 0.0


def test_spare_capacity_and_quality_ranking():
    full = _fac("full", capacity_daily=10, active_load=10, quality_score=99)
    spare = _fac("spare", capacity_daily=10, active_load=1, quality_score=10)
    out = fmatch.rank([full, spare])
    # spare capacity beats a higher-quality but full facility
    assert out[0]["id"] == "spare"


def test_hours_filter_excludes_closed_day():
    # 2026-07-29 is a Wednesday -> weekday()=2 -> our day_of_week=(2+1)%7=3
    when = datetime(2026, 7, 29, 10, 0)
    fac = _fac("f", timings={3: {"is_closed": True, "is_24h": False,
                                 "opens_at": None, "closes_at": None}})
    assert fmatch.rank([fac], when=when) == []


def test_safe_output_has_no_quality_or_rate():
    out = fmatch.rank([_fac("f", quality_score=88)])
    assert "quality_score" not in out[0]
    assert "payout_rate" not in out[0]


def test_invalidate_clears_cache():
    fmatch._cache["data"] = [_fac("x")]
    fmatch._cache["at"] = 9e9
    fmatch.invalidate()
    assert fmatch._cache["data"] is None
    assert fmatch._cache["at"] == -1.0


async def test_find_eligible_reloads_after_invalidate(monkeypatch):
    calls = {"n": 0}

    async def fake_fetch(sql, *args):
        # facilities query returns one row; others return empty.
        if "from facilities" in sql:
            calls["n"] += 1
            return [{"id": "fac-1", "code": "F1", "name": "F1", "area": "Marina",
                     "city": "Dubai", "emirate": "Dubai", "latitude": None, "longitude": None,
                     "service_radius_km": None, "capacity_daily": None,
                     "capacity_unit": "orders_per_day", "operating_status": "open",
                     "accepts_orders": True, "quality_score": None, "created_at": "2026-01-01"}]
        return []

    monkeypatch.setattr(database, "fetch", fake_fetch)
    fmatch.invalidate()
    r1 = await fmatch.find_eligible()
    assert len(r1) == 1 and calls["n"] == 1
    # cached — no reload
    await fmatch.find_eligible()
    assert calls["n"] == 1
    # after invalidate — reloads
    fmatch.invalidate()
    await fmatch.find_eligible()
    assert calls["n"] == 2
