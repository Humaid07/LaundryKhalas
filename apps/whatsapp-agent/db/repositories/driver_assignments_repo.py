"""Driver assignment reads/writes (dev/test Supabase schema).

An assignment is one order task (pickup / facility_handoff / delivery / return)
given to a facility driver. EVERY query is SCOPED to ``facility_id`` — a facility
can only ever see/act on its own assignments. Assignments carry a PII-safe
``service_summary`` (service label only) — never customer phone/address.
"""
from __future__ import annotations

from db import database

ACTIVE_STATUSES: tuple[str, ...] = ("assigned", "in_progress")

_SELECT = """
  select id, facility_id, driver_id, order_id, order_ref, task_type, service_summary,
         status, assigned_at, started_at, completed_at, expected_completion_at, area,
         notes, created_at, updated_at
    from driver_assignments
"""


def to_assignment_read(row: dict | None) -> dict | None:
    if row is None:
        return None
    return {
        "id": str(row.get("id")),
        "driver_id": str(row["driver_id"]) if row.get("driver_id") else None,
        "order_id": str(row["order_id"]) if row.get("order_id") else None,
        "order_ref": row.get("order_ref"),
        "task_type": row.get("task_type"),
        "service_summary": row.get("service_summary"),
        "status": row.get("status"),
        "assigned_at": row.get("assigned_at"),
        "started_at": row.get("started_at"),
        "completed_at": row.get("completed_at"),
        "expected_completion_at": row.get("expected_completion_at"),
        "area": row.get("area"),
        "notes": row.get("notes"),
    }


async def create(
    facility_id: str,
    *,
    driver_id: str,
    order_uuid: str | None,
    order_ref: str | None,
    task_type: str = "facility_handoff",
    service_summary: str | None = None,
    expected_completion_at=None,
    area: str | None = None,
    notes: str | None = None,
) -> dict | None:
    row = await database.fetchrow(
        """
        insert into driver_assignments
            (facility_id, driver_id, order_id, order_ref, task_type, service_summary,
             status, expected_completion_at, area, notes,
             is_test_data, is_demo, environment, created_by_seed)
        values ($1, $2, $3, $4, $5, $6, 'assigned', $7, $8, $9, true, false, 'dev', false)
        returning id, facility_id, driver_id, order_id, order_ref, task_type,
                  service_summary, status, assigned_at, started_at, completed_at,
                  expected_completion_at, area, notes, created_at, updated_at
        """,
        facility_id, driver_id, order_uuid, order_ref, task_type, service_summary,
        expected_completion_at, area, notes,
    )
    return to_assignment_read(row)


async def set_status(facility_id: str, assignment_id: str, status: str) -> dict | None:
    # Stamp started_at/completed_at on the relevant transitions.
    started = "started_at = coalesce(started_at, now())" if status == "in_progress" else "started_at = started_at"
    completed = "completed_at = now()" if status in ("completed", "cancelled") else "completed_at = completed_at"
    row = await database.fetchrow(
        f"update driver_assignments set status = $3, {started}, {completed} "
        "where id = $1 and facility_id = $2 "
        "returning id, facility_id, driver_id, order_id, order_ref, task_type, "
        "service_summary, status, assigned_at, started_at, completed_at, "
        "expected_completion_at, area, notes, created_at, updated_at",
        assignment_id, facility_id, status,
    )
    return to_assignment_read(row)


async def get(facility_id: str, assignment_id: str) -> dict | None:
    row = await database.fetchrow(
        _SELECT + " where facility_id = $1 and id::text = $2", facility_id, assignment_id
    )
    return to_assignment_read(row)


async def list_for_driver(facility_id: str, driver_id: str, *, limit: int = 50) -> list[dict]:
    rows = await database.fetch(
        _SELECT + " where facility_id = $1 and driver_id = $2 "
        "order by assigned_at desc limit $3",
        facility_id, driver_id, max(1, min(int(limit), 200)),
    )
    return [to_assignment_read(r) for r in rows]


async def active_for_driver(facility_id: str, driver_id: str) -> dict | None:
    row = await database.fetchrow(
        _SELECT + " where facility_id = $1 and driver_id = $2 "
        "and status = any($3::text[]) order by assigned_at desc limit 1",
        facility_id, driver_id, list(ACTIVE_STATUSES),
    )
    return to_assignment_read(row)


async def active_for_order(facility_id: str, order_uuid: str) -> dict | None:
    """The active assignment for an order (for the order-detail driver panel)."""
    row = await database.fetchrow(
        _SELECT + " where facility_id = $1 and order_id = $2 "
        "and status = any($3::text[]) order by assigned_at desc limit 1",
        facility_id, order_uuid, list(ACTIVE_STATUSES),
    )
    return to_assignment_read(row)


async def active_by_driver_map(facility_id: str) -> dict[str, dict]:
    """{driver_id: active_assignment} for the whole facility — one query so the
    Drivers list can compute Free/On-Job without N+1 lookups."""
    rows = await database.fetch(
        _SELECT + " where facility_id = $1 and status = any($2::text[]) "
        "order by assigned_at desc",
        facility_id, list(ACTIVE_STATUSES),
    )
    out: dict[str, dict] = {}
    for r in rows:
        did = str(r["driver_id"])
        if did not in out:  # newest wins (ordered desc)
            out[did] = to_assignment_read(r)
    return out
