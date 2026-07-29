"""Agent facility tools — grounded reads, no internal-data leakage, audited write.

Confirms: read tools are registered + strict; they return no rates/quality; the
customer tool-loop does NOT expose a facility mutation; the mutation path is
routed through the audited facility_admin with actor_type="agent".
"""
import json

from agents.whatsapp_agent import facility_tools
from agents.whatsapp_agent.llm_tools import _TOOL_NAMES, execute_tool
from db import database
from db.repositories import facilities_repo
from services import facility_admin, facility_matching


async def _call(name, **inp):
    text, err = await execute_tool(name, inp)
    return json.loads(text), err


def test_facility_read_tools_registered_and_strict():
    for schema in facility_tools.READ_TOOL_SCHEMAS:
        assert schema["name"] in _TOOL_NAMES
        assert schema["input_schema"].get("additionalProperties") is False


def test_customer_loop_has_no_facility_mutation_tool():
    # The agent may never pause/close a facility from a customer-facing turn.
    assert "update_facility_status" not in _TOOL_NAMES
    assert "agent_update_facility_status" not in _TOOL_NAMES


async def test_facility_tool_unavailable_outside_supabase(monkeypatch):
    monkeypatch.setattr(database, "is_supabase_mode", lambda: False)
    data, err = await _call("list_facilities")
    assert err is False
    assert data["available"] is False


async def test_find_eligible_output_is_safe(monkeypatch):
    monkeypatch.setattr(database, "is_supabase_mode", lambda: True)

    async def fake_find(**kw):
        return [{"id": "f1", "name": "Marina", "area": "Marina", "city": "Dubai",
                 "emirate": "Dubai", "operating_status": "open", "distance_km": None,
                 "capacity_daily": 50, "capacity_unit": "orders_per_day",
                 "has_spare_capacity": True}]
    monkeypatch.setattr(facility_matching, "find_eligible", fake_find)

    data, err = await _call("find_eligible_facilities", service="wash and fold")
    assert err is False
    assert data["count"] == 1
    entry = data["facilities"][0]
    assert "quality_score" not in entry and "payout_rate" not in entry and "rate" not in entry


async def test_list_facilities_strips_quality(monkeypatch):
    monkeypatch.setattr(database, "is_supabase_mode", lambda: True)

    async def fake_list(**kw):
        # admin rows DO carry quality_score — the tool must strip it.
        return [{"id": "f1", "code": "F1", "name": "Marina", "area": "Marina",
                 "city": "Dubai", "emirate": "Dubai", "operating_status": "open",
                 "capacity_daily": 50, "capacity_unit": "orders_per_day",
                 "quality_score": 91.0, "payout_rate": 12.0}]
    monkeypatch.setattr(facilities_repo, "list_filtered", fake_list)

    data, err = await _call("list_facilities")
    assert err is False
    entry = data["facilities"][0]
    assert "quality_score" not in entry
    assert "payout_rate" not in entry


async def test_agent_status_update_is_audited(monkeypatch):
    captured = {}

    async def fake_change(fid, status, *, actor_id=None, actor_type=None, source_app=None):
        captured.update(fid=fid, status=status, actor_type=actor_type, source_app=source_app)
        return {"id": fid, "operating_status": status}

    monkeypatch.setattr(facility_admin, "change_status", fake_change)
    result = await facility_tools.agent_update_facility_status("fac-1", "busy")
    assert result["operating_status"] == "busy"
    assert captured["actor_type"] == "agent"
    assert captured["source_app"] == "whatsapp_agent"
