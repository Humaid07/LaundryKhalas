"""Facility driver operations tests.

Covers the PURE status logic (Free vs On Job, summary counts) and the assignment
ACTION flow (facility scoping, order-event audit, mock-first notification,
role permissions). Repos are mocked — no DB needed (mirrors the facility_
notifications test pattern; facility repos are Supabase-backed).
"""
from db.repositories import (
    driver_assignments_repo,
    facility_drivers_repo,
    facility_orders_repo,
    order_events_repo,
)
from services import facility_drivers as ds
from services import facility_notifications as fn


# --------------------------- pure status derivation -----------------------
def test_free_driver_is_free():
    d = {"id": "d1", "status": "free", "active": True}
    assert ds.derive_effective_status(d, None) == "free"
    assert ds.is_free(d, None) is True


def test_driver_with_active_assignment_is_on_job():
    d = {"id": "d1", "status": "handoff_in_progress", "active": True}
    assignment = {"order_ref": "LK-1", "task_type": "facility_handoff"}
    assert ds.derive_effective_status(d, assignment) == "on_job"
    assert ds.is_free(d, assignment) is False


def test_on_break_and_offline_and_issue_are_not_free():
    assert ds.derive_effective_status({"status": "on_break", "active": True}, None) == "on_break"
    assert ds.derive_effective_status({"status": "offline", "active": True}, None) == "offline"
    assert ds.derive_effective_status({"status": "free", "active": False}, None) == "offline"
    assert ds.derive_effective_status({"status": "issue_reported", "active": True}, None) == "issue"


def test_summarize_counts():
    drivers = [
        ds.decorate({"id": "d1", "status": "free", "active": True}, None),
        ds.decorate({"id": "d2", "status": "pickup_in_progress", "active": True},
                    {"order_ref": "LK-1", "task_type": "pickup"}),
        ds.decorate({"id": "d3", "status": "on_break", "active": True}, None),
        ds.decorate({"id": "d4", "status": "issue_reported", "active": True}, None),
        ds.decorate({"id": "d5", "status": "delivery_in_progress", "active": True},
                    {"order_ref": "LK-2", "task_type": "delivery"}),
    ]
    s = ds.summarize(drivers)
    assert s["total"] == 5
    assert s["free"] == 1
    assert s["on_job"] == 2
    assert s["pickup"] == 1
    assert s["delivery"] == 1
    assert s["on_break"] == 1
    assert s["issues"] == 1


def test_free_count_drops_after_assignment():
    driver = {"id": "d1", "status": "free", "active": True}
    before = ds.summarize([ds.decorate(driver, None)])
    after = ds.summarize([ds.decorate(
        {**driver, "status": "handoff_in_progress"},
        {"order_ref": "LK-1", "task_type": "facility_handoff"})])
    assert before["free"] == 1 and before["on_job"] == 0
    assert after["free"] == 0 and after["on_job"] == 1


# --------------------------- role permissions -----------------------------
def test_can_manage_roles():
    assert ds.can_manage("facility_owner") is True
    assert ds.can_manage("facility_manager") is True
    assert ds.can_manage("admin") is True
    assert ds.can_manage("facility_staff") is False
    assert ds.can_manage("facility_driver") is False
    assert ds.can_manage(None) is False


# --------------------------- assignment action flow -----------------------
def _patch_assign(monkeypatch, *, driver=True, order=True, busy=False):
    events, notifies = [], []

    async def fake_driver_get(fid, did):
        return {"id": did, "name": "Ravi", "facility_id": fid} if driver else None

    async def fake_order_get_row(fid, oid):
        return {"id": "ordu1", "order_id": "LK-AE-1042", "service": "Wash & Fold",
                "pickup_area": "Dubai Marina"} if order else None

    async def fake_active_for_driver(fid, did):
        return {"id": "a0"} if busy else None

    async def fake_create(fid, **kw):
        return {"id": "asg1", "driver_id": kw.get("driver_id"),
                "order_ref": kw.get("order_ref"), "task_type": kw.get("task_type"),
                "status": "assigned"}

    async def fake_set_status(fid, did, status):
        return {"id": did, "status": status}

    async def fake_status_event(*a, **k):
        return {}

    async def fake_event_create(**kw):
        events.append(kw)
        return {"id": "e1", **kw}

    async def fake_order_get(fid, oid):
        return {"order_id": "LK-AE-1042", "service": "Wash & Fold"}

    async def fake_notify(fid, order_read, **kw):
        notifies.append({"facility_id": fid, **kw})
        return {"id": "n1"}

    async def fake_get_with_status(fid, did):
        return {"id": did, "effective_status": "on_job"}

    monkeypatch.setattr(facility_drivers_repo, "get", fake_driver_get)
    monkeypatch.setattr(facility_orders_repo, "get_row", fake_order_get_row)
    monkeypatch.setattr(facility_orders_repo, "get", fake_order_get)
    monkeypatch.setattr(driver_assignments_repo, "active_for_driver", fake_active_for_driver)
    monkeypatch.setattr(driver_assignments_repo, "create", fake_create)
    monkeypatch.setattr(facility_drivers_repo, "set_status", fake_set_status)
    monkeypatch.setattr(facility_drivers_repo, "add_status_event", fake_status_event)
    monkeypatch.setattr(order_events_repo, "create", fake_event_create)
    monkeypatch.setattr(fn, "notify_driver_assigned", fake_notify)
    monkeypatch.setattr(ds, "get_with_status", fake_get_with_status)
    return events, notifies


async def test_assign_creates_assignment_event_and_notifies(monkeypatch):
    events, notifies = _patch_assign(monkeypatch)
    result = await ds.assign_order_to_driver(
        "FAC-1", "d1", "LK-AE-1042", task_type="facility_handoff", actor_label="Owner")
    assert result["assignment"]["id"] == "asg1"
    # An order_events audit row is written (drives the order timeline).
    assert any(e["event_type"] == "driver_assigned" for e in events)
    # Facility contacts were notified (mock-first).
    assert len(notifies) == 1
    assert notifies[0]["task_type"] == "facility_handoff"


async def test_assign_cross_facility_order_raises(monkeypatch):
    # Order is not this facility's → get_row returns None → LookupError.
    _patch_assign(monkeypatch, order=False)
    try:
        await ds.assign_order_to_driver("FAC-1", "d1", "LK-OTHER", actor_label="Owner")
        assert False, "expected LookupError"
    except LookupError:
        pass


async def test_assign_cross_facility_driver_raises(monkeypatch):
    _patch_assign(monkeypatch, driver=False)
    try:
        await ds.assign_order_to_driver("FAC-1", "dX", "LK-AE-1042", actor_label="Owner")
        assert False, "expected LookupError"
    except LookupError:
        pass


async def test_assign_busy_driver_raises(monkeypatch):
    _patch_assign(monkeypatch, busy=True)
    try:
        await ds.assign_order_to_driver("FAC-1", "d1", "LK-AE-1042", actor_label="Owner")
        assert False, "expected DriverActionError"
    except ds.DriverActionError:
        pass
