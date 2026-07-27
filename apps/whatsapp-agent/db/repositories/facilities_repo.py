"""Facility (laundry partner) profile + overview reads against the dev/test
Supabase schema.

A facility is the partner cleaning site the Facility Dashboard is scoped to. All
reads here are already scoped by ``facility_id`` (resolved by
``api/deps.require_facility_scope``); the profile never exposes customer PII.
"""
from __future__ import annotations

from db import database

_PROFILE_COLS = (
    "id, code, name, area, city, emirate, capacity_daily, operating_status, "
    "is_active, contact_area, notes, created_at, updated_at"
)


def to_profile(row: dict) -> dict:
    """Facility profile (non-PII). ``payout_rate`` is intentionally NOT exposed —
    partner rates are internal + deferred."""
    return {
        "id": str(row["id"]),
        "code": row.get("code"),
        "name": row.get("name"),
        "area": row.get("area"),
        "city": row.get("city"),
        "emirate": row.get("emirate"),
        "capacity_daily": row.get("capacity_daily"),
        "operating_status": row.get("operating_status"),
        "is_active": bool(row.get("is_active")),
        "contact_area": row.get("contact_area"),
        "notes": row.get("notes"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


async def get(facility_id: str) -> dict | None:
    row = await database.fetchrow(
        f"select {_PROFILE_COLS} from facilities where id = $1", facility_id
    )
    return to_profile(row) if row else None


async def get_by_code(code: str) -> dict | None:
    row = await database.fetchrow(
        f"select {_PROFILE_COLS} from facilities where code = $1", code
    )
    return to_profile(row) if row else None


# Statuses that mean an order is still occupying a facility's operating capacity
# (mirrors the facility "not terminal" lanes; a draft isn't assigned yet).
_ACTIVE_LOAD_STATUSES = ("active", "pickup_scheduled", "picked_up", "in_cleaning",
                         "ready_for_delivery", "out_for_delivery")


async def select_for_location(
    area: str | None, city: str | None, emirate: str | None
) -> dict | None:
    """Pick the best facility to handle a new order, given its pickup location.

    Ranking (best first): a location match (area > city > emirate), then an
    'open' operating status over 'busy', then a facility with spare daily
    capacity, then the least-loaded, then the oldest facility for a stable
    tie-break. Only ACTIVE facilities that are not 'closed'/'paused' are
    considered. Returns the chosen facility row (with ``active_load`` and a
    ``match_basis`` label) or None when no facility can currently take work — in
    which case the order is left unassigned for ops rather than force-routed.

    No data is invented: this is purely a DB-driven operational assignment
    decision (CLAUDE.md §4/§9). All order load counting is scoped per facility.
    """
    row = await database.fetchrow(
        f"""
        select * from (
          select f.*,
            (select count(*) from orders o
              where o.facility_id = f.id
                and o.status = any($4::text[])) as active_load,
            (case
               when $1::text is not null and lower(f.area)    = lower($1::text) then 'area'
               when $2::text is not null and lower(f.city)    = lower($2::text) then 'city'
               when $3::text is not null and lower(f.emirate) = lower($3::text) then 'emirate'
               else 'fallback' end) as match_basis
          from facilities f
          where f.is_active = true
            and f.operating_status not in ('closed', 'paused')
        ) c
        order by
          (case c.match_basis when 'area' then 3 when 'city' then 2
                              when 'emirate' then 1 else 0 end) desc,
          (case when c.operating_status = 'open' then 1 else 0 end) desc,
          (case when c.capacity_daily is null then 0
                when c.active_load < c.capacity_daily then 1 else 0 end) desc,
          c.active_load asc,
          c.created_at asc
        limit 1
        """,
        area, city, emirate, list(_ACTIVE_LOAD_STATUSES),
    )
    return dict(row) if row else None


async def overview(facility_id: str) -> dict:
    """Counts + operating status for the facility overview card. All counts are
    scoped to this facility_id. 'today' uses the Asia/Dubai business day."""
    fac = await database.fetchrow(
        "select name, operating_status from facilities where id = $1", facility_id
    )
    row = await database.fetchrow(
        """
        select
          count(*) filter (
            where o.status in ('active','pickup_scheduled','picked_up','in_cleaning')
              and o.pickup_date = (now() at time zone 'Asia/Dubai')::date) as orders_in_today,
          count(*) filter (
            where o.status in ('ready_for_delivery','out_for_delivery')
              and coalesce(o.estimated_delivery_end_at, o.updated_at) at time zone 'Asia/Dubai'
                  >= (now() at time zone 'Asia/Dubai')::date) as orders_out_today,
          count(*) filter (
            where o.status not in ('draft','completed','cancelled','abandoned')
              and o.pickup_date >= (now() at time zone 'Asia/Dubai')::date) as upcoming,
          count(*) filter (
            where o.status in ('support_required','cancellation_requested','pickup_change_requested')) as needs_attention_status
        from orders o
        where o.facility_id = $1
        """,
        facility_id,
    )
    open_issues = await database.fetchval(
        "select count(*) from facility_issues where facility_id = $1 "
        "and status not in ('resolved','closed')",
        facility_id,
    )
    return {
        "name": fac["name"] if fac else None,
        "operating_status": fac["operating_status"] if fac else None,
        "orders_in_today": row["orders_in_today"] if row else 0,
        "orders_out_today": row["orders_out_today"] if row else 0,
        "upcoming": row["upcoming"] if row else 0,
        "needs_attention": (row["needs_attention_status"] if row else 0) + (open_issues or 0),
        "open_issues": open_issues or 0,
    }
