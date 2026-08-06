"""Advanced-routing integration: mode dispatch, atomic assign, manual case,
fallback, and environment-isolated candidate loading (Area C).

Supabase-only paths are exercised by monkeypatching the repos/engine (the suite
runs on SQLite), matching the other facility tests.
"""
from datetime import datetime

import pytest

from db import database
from db.repositories import routing_decisions_repo
from services import facility_routing as fr
from services.routing import candidate_loader
from services.routing import engine as routing_engine


class _S:
    def __init__(self, **k):
        base = dict(advanced_routing_enabled=True, advanced_routing_mode="live",
                    advanced_routing_canary_percentage=0, advanced_routing_fallback_to_legacy=True,
                    allow_test_facility_routing=True)
        base.update(k)
        self.__dict__.update(base)


def _order(**over):
    base = {"id": "o1", "order_id": "LK-1", "is_test_data": False, "facility_id": None,
            "pickup_area": "Deira", "city": "Dubai", "pickup_emirate": "Dubai"}
    base.update(over)
    return base


def _bundle(selected="FAC-ADV", is_test=False):
    return {
        "result": {"selected_facility_id": selected, "selected_driver_id": "d1",
                   "selected_pickup_slot_id": "slot1", "selection_reason": "best facility",
                   "eligible_count": 1 if selected else 0, "rejected_count": 0,
                   "score_components": {}, "eligible_candidates": [], "rejected_candidates": []},
        "request": {"area": "Deira", "service_code": "WASH_AND_FOLD", "required_capabilities": []},
        "when": datetime(2026, 8, 6, 12, 30), "is_test": is_test,
        "routing_version": "ADVANCED_ROUTING_V1",
    }


@pytest.fixture
def wired(monkeypatch):
    calls = {"set_facility": [], "events": [], "legacy": 0, "snapshots": []}

    async def route_order(order_row):
        return calls.get("bundle") or _bundle()

    async def set_facility(order_uuid, facility_id):
        calls["set_facility"].append((order_uuid, facility_id))
        return {"id": order_uuid}

    async def create_event(**kw):
        calls["events"].append(kw)
        return {}

    async def select_for_location(area, city, emirate):
        return {"id": "FAC-LEGACY", "code": "LEG", "name": "Legacy"}

    async def snapshot(**kw):
        calls["snapshots"].append(kw)
        return {}

    monkeypatch.setattr(routing_engine, "route_order", route_order)
    monkeypatch.setattr(fr.orders_repo, "set_facility", set_facility)
    monkeypatch.setattr(fr.order_events_repo, "create", create_event)
    monkeypatch.setattr(fr.facilities_repo, "select_for_location", select_for_location)
    monkeypatch.setattr(routing_decisions_repo, "create", snapshot)
    return calls


async def test_live_mode_assigns_advanced_selection(wired, monkeypatch):
    monkeypatch.setattr(fr, "get_settings", lambda: _S(advanced_routing_mode="live"))
    out = await fr.assign_facility_for_order(_order())
    assert out == "FAC-ADV"
    assert wired["set_facility"] == [("o1", "FAC-ADV")]
    evt = wired["events"][0]
    assert evt["event_type"] == "facility_assigned"
    assert evt["metadata"]["routing_engine"] == "advanced"


async def test_shadow_mode_lets_legacy_assign_and_records_comparison(wired, monkeypatch):
    monkeypatch.setattr(fr, "get_settings", lambda: _S(advanced_routing_mode="shadow"))
    out = await fr.assign_facility_for_order(_order())
    # legacy assigns FAC-LEGACY; advanced selection (FAC-ADV) only recorded.
    assert out == "FAC-LEGACY"
    assert wired["set_facility"] == [("o1", "FAC-LEGACY")]
    snap = wired["snapshots"][-1]
    assert snap["routing_mode"] == "shadow"
    assert snap["advanced_selected_facility_id"] == "FAC-ADV"
    assert snap["selections_matched"] is False  # FAC-LEGACY != FAC-ADV


async def test_no_eligible_opens_manual_case_no_legacy_bypass(wired, monkeypatch):
    wired["bundle"] = _bundle(selected=None)
    monkeypatch.setattr(fr, "get_settings", lambda: _S(advanced_routing_mode="live"))
    out = await fr.assign_facility_for_order(_order())
    assert out is None
    assert wired["set_facility"] == []                      # nothing assigned
    assert wired["events"][0]["event_type"] == "routing_manual_required"


async def test_error_falls_back_to_legacy_for_production(wired, monkeypatch):
    async def boom(order_row):
        raise RuntimeError("engine down")

    monkeypatch.setattr(routing_engine, "route_order", boom)
    monkeypatch.setattr(fr, "get_settings", lambda: _S(advanced_routing_mode="live"))
    out = await fr.assign_facility_for_order(_order())
    assert out == "FAC-LEGACY"                              # safe fallback
    assert wired["events"][-1]["metadata"]["fallback_used"] is True


async def test_test_order_never_falls_back_to_legacy(wired, monkeypatch):
    async def boom(order_row):
        raise RuntimeError("engine down")

    monkeypatch.setattr(routing_engine, "route_order", boom)
    monkeypatch.setattr(fr, "get_settings", lambda: _S(advanced_routing_mode="live"))
    out = await fr.assign_facility_for_order(_order(is_test_data=True))
    assert out is None                                      # test orders never touch legacy/real facilities
    assert wired["set_facility"] == []


async def test_advanced_off_uses_legacy(wired, monkeypatch):
    monkeypatch.setattr(fr, "get_settings", lambda: _S(advanced_routing_enabled=False, advanced_routing_mode="off"))
    out = await fr.assign_facility_for_order(_order())
    assert out == "FAC-LEGACY"
    # advanced engine never consulted (no snapshot).
    assert wired["snapshots"] == []


async def test_already_assigned_is_idempotent(wired, monkeypatch):
    monkeypatch.setattr(fr, "get_settings", lambda: _S())
    out = await fr.assign_facility_for_order(_order(facility_id="FAC-EXISTING"))
    assert out == "FAC-EXISTING"
    assert wired["set_facility"] == []


# ---------------------------- candidate loader ---------------------------
async def test_loader_isolates_environment(monkeypatch):
    captured = {}

    async def fake_fetch(sql, *args):
        captured.setdefault("calls", []).append((sql, args))
        if "from facilities" in sql:
            return []          # short-circuit (no facilities) so we only assert the guard
        return []

    monkeypatch.setattr(database, "fetch", fake_fetch)
    await candidate_loader.load_candidates(is_test=True)
    fac_sql, fac_args = captured["calls"][0]
    assert "is_test_facility = $1" in fac_sql
    assert fac_args[0] is True     # test order loads ONLY test facilities
