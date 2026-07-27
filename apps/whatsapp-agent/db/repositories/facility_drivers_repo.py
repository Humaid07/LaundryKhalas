"""Facility-SCOPED driver reads/writes against the dev/test Supabase schema.

EVERY query filters ``facility_id = $1`` — a facility can only ever see/act on
its OWN drivers (the isolation boundary, together with
``api/deps.require_facility_scope``; the service role bypasses RLS). A driver row
is PII-safe: ``to_driver_read`` returns the driver's MASKED phone only and never
any customer data (CLAUDE.md §7).

The driver's *effective* status (Free vs On Job …) is derived in
``services/facility_drivers.py`` from the stored ``status`` + the active
assignment, so this repo stays a thin data-access layer.
"""
from __future__ import annotations

from services.privacy import mask_phone
from db import database

_SELECT = """
  select id, facility_id, user_id, name, phone_masked, role, status, vehicle_type,
         area, active, last_active_at, created_at, updated_at
    from facility_drivers
"""


def to_driver_read(row: dict | None) -> dict | None:
    """PII-safe driver view — MASKED phone only, never the full number."""
    if row is None:
        return None
    return {
        "id": str(row.get("id")),
        "facility_id": str(row.get("facility_id")) if row.get("facility_id") else None,
        "user_id": str(row["user_id"]) if row.get("user_id") else None,
        "name": row.get("name"),
        "masked_phone": row.get("phone_masked"),
        "role": row.get("role"),
        "status": row.get("status"),
        "vehicle_type": row.get("vehicle_type"),
        "area": row.get("area"),
        "active": bool(row.get("active")),
        "last_active_at": row.get("last_active_at"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


async def list_drivers(facility_id: str, *, active_only: bool = False) -> list[dict]:
    where = " where facility_id = $1"
    if active_only:
        where += " and active = true"
    rows = await database.fetch(
        _SELECT + where + " order by name asc", facility_id
    )
    return [to_driver_read(r) for r in rows]


async def get(facility_id: str, driver_id: str) -> dict | None:
    row = await database.fetchrow(
        _SELECT + " where facility_id = $1 and id::text = $2", facility_id, driver_id
    )
    return to_driver_read(row)


async def get_row(facility_id: str, driver_id: str) -> dict | None:
    """Raw row (incl. phone_e164) SCOPED to the facility — for internal use."""
    return await database.fetchrow(
        "select * from facility_drivers where facility_id = $1 and id::text = $2",
        facility_id, driver_id,
    )


async def create(
    facility_id: str,
    *,
    name: str,
    phone_e164: str | None = None,
    role: str = "driver",
    vehicle_type: str | None = None,
    area: str | None = None,
    active: bool = True,
    user_id: str | None = None,
) -> dict | None:
    row = await database.fetchrow(
        """
        insert into facility_drivers
            (facility_id, user_id, name, phone_e164, phone_masked, role, vehicle_type,
             area, active, is_test_data, is_demo, environment, created_by_seed)
        values ($1, $2, $3, $4, $5, $6, $7, $8, $9, true, false, 'dev', false)
        returning id, facility_id, user_id, name, phone_masked, role, status,
                  vehicle_type, area, active, last_active_at, created_at, updated_at
        """,
        facility_id, user_id, name, phone_e164,
        mask_phone(phone_e164) if phone_e164 else None,
        role, vehicle_type, area, active,
    )
    return to_driver_read(row)


async def update(
    facility_id: str,
    driver_id: str,
    *,
    name: str | None = None,
    role: str | None = None,
    phone_e164: str | None = None,
    vehicle_type: str | None = None,
    area: str | None = None,
    active: bool | None = None,
    status: str | None = None,
) -> dict | None:
    sets: list[str] = []
    params: list = [driver_id, facility_id]

    def st(col, val, cast=""):
        params.append(val)
        sets.append(f"{col} = ${len(params)}{cast}")

    if name is not None:
        st("name", name)
    if role is not None:
        st("role", role)
    if phone_e164 is not None:
        st("phone_e164", phone_e164)
        st("phone_masked", mask_phone(phone_e164))
    if vehicle_type is not None:
        st("vehicle_type", vehicle_type)
    if area is not None:
        st("area", area)
    if active is not None:
        st("active", active)
    if status is not None:
        st("status", status)
    if not sets:
        return await get(facility_id, driver_id)
    row = await database.fetchrow(
        f"update facility_drivers set {', '.join(sets)} "
        "where id = $1 and facility_id = $2 "
        "returning id, facility_id, user_id, name, phone_masked, role, status, "
        "vehicle_type, area, active, last_active_at, created_at, updated_at",
        *params,
    )
    return to_driver_read(row)


async def set_status(facility_id: str, driver_id: str, status: str) -> dict | None:
    row = await database.fetchrow(
        "update facility_drivers set status = $3, last_active_at = now() "
        "where id = $1 and facility_id = $2 "
        "returning id, facility_id, user_id, name, phone_masked, role, status, "
        "vehicle_type, area, active, last_active_at, created_at, updated_at",
        driver_id, facility_id, status,
    )
    return to_driver_read(row)


async def add_status_event(
    facility_id: str,
    driver_id: str,
    status: str,
    *,
    order_uuid: str | None = None,
    note: str | None = None,
    created_by: str | None = None,
) -> dict | None:
    return await database.fetchrow(
        """
        insert into driver_status_events
            (facility_id, driver_id, status, order_id, note, created_by,
             is_test_data, is_demo, environment, created_by_seed)
        values ($1, $2, $3, $4, $5, $6, true, false, 'dev', false)
        returning id, facility_id, driver_id, status, order_id, note, created_by, created_at
        """,
        facility_id, driver_id, status, order_uuid, note, created_by,
    )


async def status_counts(facility_id: str) -> dict:
    """Raw per-status counts for the facility's ACTIVE drivers (the service maps
    these into Free / On Job / Issues summary tiles)."""
    rows = await database.fetch(
        "select status, count(*) as n from facility_drivers "
        "where facility_id = $1 and active = true group by status",
        facility_id,
    )
    return {r["status"]: int(r["n"]) for r in rows}
