"""Stage 4 — route-to-human specialist categories (spec §2.8): villa/home cleaning,
wedding dresses, luxury/couture care. Pure classifier + the route_to_specialist
tool + the service_resolution integration. Offline.
"""
from __future__ import annotations

import datetime as _dt
import json

import pytest

from agents.whatsapp_agent.booking_tools import BookingContext, make_booking_executor
from services import booking_flow as bf
from services import order_store, service_resolution, specialty_routing


@pytest.fixture(autouse=True)
def _fresh():
    specialty_routing.reload_routing()
    yield
    specialty_routing.reload_routing()


# --------------------------------------------------------------------------
# Pure classifier
# --------------------------------------------------------------------------
@pytest.mark.parametrize("text,category", [
    ("I need villa cleaning", "HOME_CLEANING"),
    ("deep clean for my apartment", "HOME_CLEANING"),
    ("office cleaning service", "HOME_CLEANING"),
    ("re-dye my couture jacket", "LUXURY_BESPOKE"),
    ("exotic leather bag restoration", "LUXURY_BESPOKE"),
])
def test_classify_routes(text, category):
    m = specialty_routing.classify(text)
    assert m is not None and m.category == category


@pytest.mark.parametrize("text", [
    "wash and fold please", "5 shirts clean and press", "dry cleaning", "carpet cleaning",
])
def test_ordinary_laundry_not_routed(text):
    assert specialty_routing.classify(text) is None


# --------------------------------------------------------------------------
# service_resolution integration — routing wins over catalogue aliasing
# --------------------------------------------------------------------------
def test_wedding_dress_is_quoted_not_routed():
    # Founder 2026-08 rules: wedding dresses are QUOTED (From AED 150 + inspection/
    # photo), no longer silently routed to a human. The specialty router no longer
    # owns this phrase.
    res = service_resolution.classify_service_request("wedding dress")
    assert res.kind is service_resolution.ServiceKind.ALIAS
    assert res.routing_category is None
    assert res.is_supported is True    # a directly-quotable catalogue service now


def test_villa_cleaning_routes_not_unsupported():
    res = service_resolution.classify_service_request("villa deep cleaning")
    assert res.kind is service_resolution.ServiceKind.ROUTE
    assert res.routing_category == "HOME_CLEANING"


def test_haircut_still_unsupported_not_routed():
    res = service_resolution.classify_service_request("haircut")
    assert res.kind is service_resolution.ServiceKind.UNSUPPORTED


# --------------------------------------------------------------------------
# Tool wiring
# --------------------------------------------------------------------------
class _Repo:
    def __init__(self):
        self.row = {"id": "o1", "order_id": "LK-1", "conversation_id": "c1",
                    "status": order_store.DRAFT, "conversation_state": bf.WAITING_FOR_SERVICE}

    async def get_active_draft(self, conversation_id):
        return self.row if self.row["status"] == order_store.DRAFT else None

    async def apply_booking_updates(self, order_uuid, updates, state):
        self.row.update({k: v for k, v in (updates or {}).items() if not k.startswith("_touch")})
        self.row["conversation_state"] = state
        return self.row

    async def get_latest_for_conversation(self, conversation_id):
        return self.row


async def _slots(*a, **k):
    return []


def _ctx(repo):
    return BookingContext(conversation_id="c1", order_uuid="o1", repo=repo,
                          today=_dt.date(2026, 7, 29), available_slots=_slots, market="AE")


async def _call(execute, tool, **inp):
    text, is_error = await execute(tool, inp)
    return json.loads(text), is_error


async def test_save_service_selection_flags_route_without_creating_booking():
    # Villa/home cleaning is still a route-to-specialist category (wedding dress is
    # now quoted, so it no longer exercises the routing path).
    repo = _Repo()
    data, err = await _call(make_booking_executor(_ctx(repo)),
                            "save_service_selection", service="villa deep cleaning")
    assert err is False
    assert data["route_to_specialist"] is True
    assert data["routing_category"] == "HOME_CLEANING"
    assert data["capture_fields"]           # non-empty guidance on what to collect
    # No laundry booking was created for the routed request.
    assert not repo.row.get("service_id")


async def test_route_to_specialist_tool_logs_task_and_acks(monkeypatch):
    captured = {}

    async def _create(task_type, **kw):
        captured["task_type"] = task_type
        captured["notes"] = kw.get("notes")
        return {"task_ref": "TASK-99"}

    from db.repositories import pending_tasks_repo
    monkeypatch.setattr(pending_tasks_repo, "create", _create)

    repo = _Repo()
    data, err = await _call(make_booking_executor(_ctx(repo)),
                            "route_to_specialist", category="HOME_CLEANING",
                            details="3-bed villa deep clean, JLT, prefers weekend")
    assert err is False
    assert data["routed"] is True
    assert data["reference"] == "TASK-99"
    assert captured["task_type"] == "AWAITING_OPERATIONS_RESPONSE"
    assert "HOME_CLEANING" in captured["notes"]
    assert "specialist" in data["message"].lower()


async def test_route_to_specialist_rejects_unknown_category():
    repo = _Repo()
    _data, err = await _call(make_booking_executor(_ctx(repo)),
                             "route_to_specialist", category="NONSENSE", details="x")
    assert err is True
