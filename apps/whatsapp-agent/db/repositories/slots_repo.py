"""Pickup-slot catalogue + availability (dev/test Supabase schema).

The booking state machine reads bookable pickup windows ONLY from here — it never
invents a slot. Availability is capacity-aware and scoped by weekday, emirate and
service where the slot row narrows it (null scope = applies to everything).
"""
from __future__ import annotations

import datetime as _dt

from db import database

# Draft/cancelled bookings do not reserve capacity; everything else does.
_NON_RESERVING = ("draft", "cancelled")


def _pg_dow(d: _dt.date) -> int:
    """Postgres dow: 0=Sunday .. 6=Saturday (matches the pickup_slots.weekdays seed)."""
    return d.isoweekday() % 7


async def available_slots(
    pickup_date: _dt.date | None,
    emirate: str | None = None,
    service_id: str | None = None,
) -> list[dict]:
    """Active slots bookable on ``pickup_date`` (weekday allowed, in-scope for the
    emirate/service, and not at capacity), ordered for display. Returns dicts with
    ``slot_id, label, start_time (time), end_time (time)``."""
    if pickup_date is None:
        return []
    rows = await database.fetch(
        """
        select s.slot_id, s.label, s.start_time, s.end_time, s.capacity,
               coalesce((
                   select count(*) from orders o
                    where o.pickup_slot_id = s.slot_id
                      and o.pickup_date = $1
                      and o.status <> all($3::text[])
               ), 0) as booked
          from pickup_slots s
         where s.active
           and $2 = any(s.weekdays)
           and (s.emirate is null or lower(s.emirate) = lower($4))
           and (s.service_id is null or s.service_id = $5)
         order by s.sort_order, s.start_time
        """,
        pickup_date,
        _pg_dow(pickup_date),
        list(_NON_RESERVING),
        emirate,
        service_id,
    )
    return [
        {"slot_id": r["slot_id"], "label": r["label"],
         "start_time": r["start_time"], "end_time": r["end_time"]}
        for r in rows
        if r["booked"] < r["capacity"]
    ]


async def get_slot(slot_id: str) -> dict | None:
    return await database.fetchrow(
        "select slot_id, label, start_time, end_time, capacity, active "
        "from pickup_slots where slot_id = $1",
        slot_id,
    )


async def list_definitions() -> list[dict]:
    """All active slot definitions (for the admin/scheduling views)."""
    return await database.fetch(
        "select slot_id, label, start_time, end_time, weekdays, emirate, service_id, "
        "capacity, active, sort_order from pickup_slots where active order by sort_order"
    )
