"""Facility driver operations — status derivation + order-task assignment.

The Facility Dashboard → Drivers section shows who is Free vs On Job and which
order/task each driver is handling. This service holds:

  * the PURE status logic (``derive_effective_status`` / ``is_free`` /
    ``summarize``) that the Drivers page and tests rely on, and
  * the ACTION flow (``assign_order_to_driver`` / ``update_assignment_status`` /
    ``set_driver_status``) which is role-guarded at the API, writes an
    ``order_events`` audit row, updates driver status, and fires a MOCK-first
    facility notification (services/facility_notifications.py).

Nothing here exposes customer PII: only the service label + area travel onto an
assignment / notification (CLAUDE.md §7).
"""
from __future__ import annotations

from db.repositories import (
    driver_assignments_repo,
    facility_drivers_repo,
    facility_orders_repo,
    order_events_repo,
)
from services import facility_notifications as facility_notify

# Full stored driver-status vocabulary (mirrors the DB CHECK constraint).
DRIVER_STATUSES: tuple[str, ...] = (
    "free", "assigned", "pickup_in_progress", "on_job", "at_facility",
    "handoff_in_progress", "delivery_in_progress", "completed_recently",
    "on_break", "offline", "issue_reported",
)
TASK_TYPES: tuple[str, ...] = ("pickup", "facility_handoff", "delivery", "return")

# Roles allowed to MUTATE drivers/assignments (view is open to all facility roles).
MANAGE_ROLES: frozenset[str] = frozenset({"admin", "facility_owner", "facility_manager"})

# task_type → the driver status to set while that task is active.
_TASK_STATUS: dict[str, str] = {
    "pickup": "pickup_in_progress",
    "facility_handoff": "handoff_in_progress",
    "delivery": "delivery_in_progress",
    "return": "on_job",
}


def can_manage(role: str | None) -> bool:
    """Owner/manager (or platform admin) may create drivers + assign/unassign."""
    return (role or "") in MANAGE_ROLES


# --------------------------------------------------------------------------
# Pure status derivation (unit-tested; no DB)
# --------------------------------------------------------------------------
def derive_effective_status(driver: dict, active_assignment: dict | None) -> str:
    """Effective operational status for the summary tiles / tabs.

    Free requires: active driver, no active assignment, not on break/offline, no
    blocking issue. Any active (assigned/in_progress) assignment ⇒ On Job.
    """
    status = (driver or {}).get("status")
    if status == "issue_reported":
        return "issue"
    if not (driver or {}).get("active", True) or status == "offline":
        return "offline"
    if status == "on_break":
        return "on_break"
    if active_assignment is not None:
        return "on_job"
    return "free"


def is_free(driver: dict, active_assignment: dict | None) -> bool:
    return derive_effective_status(driver, active_assignment) == "free"


def decorate(driver: dict, active_assignment: dict | None) -> dict:
    """Driver read + derived operational fields for the Drivers page."""
    eff = derive_effective_status(driver, active_assignment)
    return {
        **driver,
        "effective_status": eff,
        "is_free": eff == "free",
        "current_assignment": active_assignment,
        "current_order_ref": (active_assignment or {}).get("order_ref"),
        "current_task": (active_assignment or {}).get("task_type"),
    }


def summarize(decorated_drivers: list[dict]) -> dict:
    """Summary tile / tab counts over already-decorated drivers."""
    counts = {"total": 0, "free": 0, "on_job": 0, "pickup": 0, "delivery": 0,
              "on_break": 0, "offline": 0, "issues": 0}
    for d in decorated_drivers:
        counts["total"] += 1
        eff = d.get("effective_status")
        if eff == "free":
            counts["free"] += 1
        elif eff == "on_job":
            counts["on_job"] += 1
        elif eff == "on_break":
            counts["on_break"] += 1
        elif eff == "offline":
            counts["offline"] += 1
        elif eff == "issue":
            counts["issues"] += 1
        task = d.get("current_task")
        if task == "pickup":
            counts["pickup"] += 1
        elif task == "delivery":
            counts["delivery"] += 1
    return counts


# --------------------------------------------------------------------------
# Reads (compose driver rows with their active assignment)
# --------------------------------------------------------------------------
async def list_with_status(facility_id: str) -> dict:
    """Every facility driver decorated with derived status + a summary block."""
    drivers = await facility_drivers_repo.list_drivers(facility_id)
    active_map = await driver_assignments_repo.active_by_driver_map(facility_id)
    decorated = [decorate(d, active_map.get(d["id"])) for d in drivers]
    return {"drivers": decorated, "summary": summarize(decorated)}


async def get_with_status(facility_id: str, driver_id: str) -> dict | None:
    driver = await facility_drivers_repo.get(facility_id, driver_id)
    if driver is None:
        return None
    active = await driver_assignments_repo.active_for_driver(facility_id, driver_id)
    return decorate(driver, active)


# --------------------------------------------------------------------------
# Actions (role-guarded at the API; audited + notified here)
# --------------------------------------------------------------------------
class DriverActionError(ValueError):
    """A driver action failed a business rule (e.g. driver already busy)."""


async def assign_order_to_driver(
    facility_id: str,
    driver_id: str,
    order_id: str,
    *,
    task_type: str = "facility_handoff",
    actor_label: str = "Facility",
    expected_completion_at=None,
    notes: str | None = None,
) -> dict:
    """Assign an order task to a driver. Enforces facility ownership of BOTH the
    driver and the order (cross-facility raises ``LookupError``), writes an
    ``order_events`` row + driver status event, and fires a mock-first facility
    notification. Raises ``DriverActionError`` if the driver is already busy."""
    if task_type not in TASK_TYPES:
        raise DriverActionError(f"Unknown task type: {task_type}.")
    driver = await facility_drivers_repo.get(facility_id, driver_id)
    if driver is None:
        raise LookupError("Driver not found for this facility.")
    order_row = await facility_orders_repo.get_row(facility_id, order_id)
    if order_row is None:
        raise LookupError("Order not found for this facility.")
    if await driver_assignments_repo.active_for_driver(facility_id, driver_id) is not None:
        raise DriverActionError(f"{driver['name']} already has an active task.")

    order_uuid = str(order_row["id"])
    order_ref = order_row.get("order_id")
    service_summary = order_row.get("service_display_name") or order_row.get("service") or "Laundry"
    area = order_row.get("pickup_area") or order_row.get("area")

    assignment = await driver_assignments_repo.create(
        facility_id, driver_id=driver_id, order_uuid=order_uuid, order_ref=order_ref,
        task_type=task_type, service_summary=service_summary,
        expected_completion_at=expected_completion_at, area=area, notes=notes,
    )
    new_status = _TASK_STATUS.get(task_type, "on_job")
    await facility_drivers_repo.set_status(facility_id, driver_id, new_status)
    await facility_drivers_repo.add_status_event(
        facility_id, driver_id, new_status, order_uuid=order_uuid,
        note=f"Assigned {task_type.replace('_', ' ')} for {order_ref}", created_by=actor_label,
    )
    await order_events_repo.create(
        order_uuid=order_uuid, event_type="driver_assigned", actor_type="facility",
        actor_name=actor_label,
        notes=f"{driver['name']} assigned for {task_type.replace('_', ' ')}.",
        metadata={"driver_id": driver_id, "task_type": task_type,
                  "assignment_id": (assignment or {}).get("id")},
    )
    order_read = await facility_orders_repo.get(facility_id, order_id)
    await facility_notify.notify_driver_assigned(
        facility_id, order_read or {"order_id": order_ref},
        task_type=task_type, expected_completion=expected_completion_at, driver_id=driver_id,
    )
    return {"assignment": assignment, "driver": await get_with_status(facility_id, driver_id)}


async def update_assignment_status(
    facility_id: str, assignment_id: str, status: str, *, actor_label: str = "Facility",
) -> dict:
    """Advance/close an assignment. On completed/cancelled the driver is freed
    (when no other active task); an issue flips the driver to issue_reported."""
    if status not in ("assigned", "in_progress", "completed", "cancelled", "issue"):
        raise DriverActionError(f"Unknown assignment status: {status}.")
    assignment = await driver_assignments_repo.get(facility_id, assignment_id)
    if assignment is None:
        raise LookupError("Assignment not found for this facility.")
    updated = await driver_assignments_repo.set_status(facility_id, assignment_id, status)
    driver_id = assignment["driver_id"]

    if status in ("completed", "cancelled"):
        if await driver_assignments_repo.active_for_driver(facility_id, driver_id) is None:
            free_status = "completed_recently" if status == "completed" else "free"
            await facility_drivers_repo.set_status(facility_id, driver_id, free_status)
            await facility_drivers_repo.add_status_event(
                facility_id, driver_id, free_status, note=f"Task {status}", created_by=actor_label)
    elif status == "issue":
        await facility_drivers_repo.set_status(facility_id, driver_id, "issue_reported")
        await facility_drivers_repo.add_status_event(
            facility_id, driver_id, "issue_reported", note="Task issue reported", created_by=actor_label)

    if assignment.get("order_id"):
        await order_events_repo.create(
            order_uuid=assignment["order_id"], event_type=f"driver_task_{status}",
            actor_type="facility", actor_name=actor_label,
            notes=f"Driver task {status} ({assignment.get('task_type')}).",
            metadata={"assignment_id": assignment_id, "driver_id": driver_id},
        )
    return updated or {}


async def set_driver_status(
    facility_id: str, driver_id: str, status: str, *, actor_label: str = "Facility",
    note: str | None = None,
) -> dict:
    if status not in DRIVER_STATUSES:
        raise DriverActionError(f"Unknown driver status: {status}.")
    driver = await facility_drivers_repo.set_status(facility_id, driver_id, status)
    if driver is None:
        raise LookupError("Driver not found for this facility.")
    await facility_drivers_repo.add_status_event(
        facility_id, driver_id, status, note=note, created_by=actor_label)
    return driver
