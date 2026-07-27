"""Facility routing tests — location selection SQL, idempotent assignment, and
the assign-on-confirm orchestration (skip / assign / never-raise).

Supabase-only DB paths are exercised by capturing the SQL/args built rather than
hitting Postgres (the ``client`` suite runs against SQLite).
"""
import pytest

from db import database
from db.repositories import facilities_repo, order_events_repo, orders_repo
from services import facility_routing as routing


# --------------------------- select_for_location -------------------------
async def test_select_for_location_ranks_area_then_capacity(monkeypatch):
    captured = {}

    async def fake_fetchrow(sql, *args):
        captured["sql"] = sql
        captured["args"] = args
        return {"id": "fac-1", "code": "FAC-DXB-MARINA", "match_basis": "area"}

    monkeypatch.setattr(database, "fetchrow", fake_fetchrow)
    result = await facilities_repo.select_for_location("Dubai Marina", "Dubai", "Dubai")

    assert result["code"] == "FAC-DXB-MARINA"
    sql = captured["sql"]
    # Only active, workable facilities are candidates.
    assert "f.is_active = true" in sql
    assert "operating_status not in ('closed', 'paused')" in sql
    # Location match is the primary ranking key (area > city > emirate).
    assert "when 'area' then 3 when 'city' then 2" in sql
    # Spare-capacity + least-loaded tie-breaks are present.
    assert "active_load < c.capacity_daily" in sql
    assert "c.active_load asc" in sql
    # Location args are bound in order; load statuses are the active lanes.
    assert captured["args"][:3] == ("Dubai Marina", "Dubai", "Dubai")
    assert "pickup_scheduled" in captured["args"][3]


async def test_select_for_location_returns_none_when_no_facility(monkeypatch):
    async def fake_fetchrow(sql, *args):
        return None

    monkeypatch.setattr(database, "fetchrow", fake_fetchrow)
    assert await facilities_repo.select_for_location("Nowhere", None, None) is None


# --------------------------- set_facility (idempotent) -------------------
async def test_set_facility_is_guarded_by_null(monkeypatch):
    captured = {}

    async def fake_fetchrow(sql, *args):
        captured["sql"] = sql
        captured["args"] = args
        return {"id": "o1", "facility_id": "fac-1"}

    monkeypatch.setattr(database, "fetchrow", fake_fetchrow)
    await orders_repo.set_facility("o1", "fac-1")
    # The null-guard is what makes assignment happen-once (no reassignment).
    assert "facility_id is null" in captured["sql"]
    assert captured["args"] == ("o1", "fac-1")


# --------------------------- assign_facility_for_order -------------------
async def test_assign_skips_when_already_assigned(monkeypatch):
    calls = {"select": 0, "set": 0}

    async def fake_select(*a, **k):
        calls["select"] += 1
        return {"id": "fac-x"}

    monkeypatch.setattr(facilities_repo, "select_for_location", fake_select)
    monkeypatch.setattr(orders_repo, "set_facility",
                        lambda *a, **k: calls.__setitem__("set", calls["set"] + 1))

    result = await routing.assign_facility_for_order(
        {"id": "o1", "order_id": "LK-1", "facility_id": "fac-existing"})
    # Returns the existing facility, never selects or writes.
    assert result == "fac-existing"
    assert calls == {"select": 0, "set": 0}


async def test_assign_selects_sets_and_audits(monkeypatch):
    events = []

    async def fake_select(area, city, emirate):
        assert (area, city, emirate) == ("Dubai Marina", "Dubai", "Dubai")
        return {"id": "fac-1", "code": "FAC-DXB-MARINA",
                "name": "Dubai Marina Facility", "match_basis": "area"}

    async def fake_set(order_uuid, facility_id):
        assert (order_uuid, facility_id) == ("o1", "fac-1")
        return {"id": "o1", "facility_id": "fac-1"}

    async def fake_event(**kwargs):
        events.append(kwargs)
        return {"id": "ev1"}

    monkeypatch.setattr(facilities_repo, "select_for_location", fake_select)
    monkeypatch.setattr(orders_repo, "set_facility", fake_set)
    monkeypatch.setattr(order_events_repo, "create", fake_event)

    result = await routing.assign_facility_for_order({
        "id": "o1", "order_id": "LK-1", "facility_id": None,
        "pickup_area": "Dubai Marina", "city": "Dubai", "pickup_emirate": "Dubai",
    })
    assert result == "fac-1"
    assert len(events) == 1
    ev = events[0]
    assert ev["event_type"] == "facility_assigned"
    assert ev["actor_type"] == "system"
    assert ev["metadata"]["facility_id"] == "fac-1"
    assert ev["metadata"]["match_basis"] == "area"


async def test_assign_returns_none_when_no_candidate(monkeypatch):
    async def fake_select(*a, **k):
        return None

    monkeypatch.setattr(facilities_repo, "select_for_location", fake_select)
    result = await routing.assign_facility_for_order(
        {"id": "o1", "order_id": "LK-1", "facility_id": None, "area": "X"})
    assert result is None


async def test_assign_never_raises(monkeypatch):
    async def boom(*a, **k):
        raise RuntimeError("db down")

    monkeypatch.setattr(facilities_repo, "select_for_location", boom)
    # A routing failure must not propagate into the booking-confirmation flow.
    result = await routing.assign_facility_for_order(
        {"id": "o1", "order_id": "LK-1", "facility_id": None})
    assert result is None


async def test_assign_none_when_lost_race(monkeypatch):
    async def fake_select(*a, **k):
        return {"id": "fac-1", "code": "FAC-1", "match_basis": "fallback"}

    async def fake_set(order_uuid, facility_id):
        return None  # someone assigned it first

    monkeypatch.setattr(facilities_repo, "select_for_location", fake_select)
    monkeypatch.setattr(orders_repo, "set_facility", fake_set)
    result = await routing.assign_facility_for_order(
        {"id": "o1", "order_id": "LK-1", "facility_id": None})
    assert result is None
