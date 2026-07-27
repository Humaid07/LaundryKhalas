"""Facility settings: operations prefs, weekly timings, blackout dates, team
members, price-change requests + agreed-price view (dev/test Supabase schema).

Every read/write is scoped by ``facility_id``. Team member phones are stored full
(backend-only) + masked for display; the read APIs return the masked value only.
Facilities can VIEW agreed pricing and REQUEST a change — they never edit the
published customer price directly (CLAUDE.md §5/§6).
"""
from __future__ import annotations

from db.repositories import catalogue_repo
from services.privacy import mask_phone
from db import database

# --- operations settings (one row per facility) ----------------------------
_SETTINGS_COLS = (
    "id, facility_id, accepting_orders, daily_capacity, service_capacity_json, "
    "quality_check_required, preferred_handoff_window, operations_config_json, "
    "created_at, updated_at"
)
_SETTINGS_FIELDS = frozenset({
    "accepting_orders", "daily_capacity", "service_capacity_json",
    "quality_check_required", "preferred_handoff_window", "operations_config_json",
})
_SETTINGS_JSONB = frozenset({"service_capacity_json", "operations_config_json"})


async def get_settings(facility_id: str) -> dict | None:
    return await database.fetchrow(
        f"select {_SETTINGS_COLS} from facility_settings where facility_id = $1",
        facility_id,
    )


async def update_settings(facility_id: str, **fields) -> dict | None:
    """Upsert the facility_settings row (one per facility)."""
    data = {k: v for k, v in fields.items() if k in _SETTINGS_FIELDS and v is not None}
    existing = await get_settings(facility_id)
    if existing is None:
        cols = ["facility_id"]
        vals = ["$1"]
        params: list = [facility_id]
        for col, val in data.items():
            params.append(val)
            cast = "::jsonb" if col in _SETTINGS_JSONB else ""
            cols.append(col)
            vals.append(f"${len(params)}{cast}")
        await database.execute(
            f"insert into facility_settings ({', '.join(cols)}, is_test_data, "
            f"is_demo, environment, created_by_seed) "
            f"values ({', '.join(vals)}, true, false, 'dev', false)",
            *params,
        )
        return await get_settings(facility_id)
    if not data:
        return existing
    sets: list[str] = []
    params = [facility_id]
    for col, val in data.items():
        params.append(val)
        cast = "::jsonb" if col in _SETTINGS_JSONB else ""
        sets.append(f"{col} = ${len(params)}{cast}")
    return await database.fetchrow(
        f"update facility_settings set {', '.join(sets)} where facility_id = $1 "
        f"returning {_SETTINGS_COLS}",
        *params,
    )


# --- weekly timings --------------------------------------------------------
_TIMING_COLS = (
    "id, facility_id, day_of_week, opens_at, closes_at, receiving_start, "
    "receiving_end, handoff_start, handoff_end, same_day_cutoff, is_closed, "
    "created_at, updated_at"
)
_TIMING_TIME_FIELDS = ("opens_at", "closes_at", "receiving_start", "receiving_end",
                       "handoff_start", "handoff_end", "same_day_cutoff")


async def list_timings(facility_id: str) -> list[dict]:
    return await database.fetch(
        f"select {_TIMING_COLS} from facility_timings where facility_id = $1 "
        "order by day_of_week asc",
        facility_id,
    )


async def upsert_timing(facility_id: str, day_of_week: int, **times) -> dict | None:
    """Upsert one day's timing row (unique on facility_id + day_of_week). Time
    fields accept 'HH:MM' strings (cast to time) or None."""
    is_closed = bool(times.get("is_closed", False))
    values = [facility_id, int(day_of_week)]
    for f in _TIMING_TIME_FIELDS:
        values.append(times.get(f))
    values.append(is_closed)
    # $3..$9 are the time fields, cast text→time so 'HH:MM' works.
    time_ph = ", ".join(f"${i}::text::time" for i in range(3, 3 + len(_TIMING_TIME_FIELDS)))
    closed_ph = f"${3 + len(_TIMING_TIME_FIELDS)}"
    update_sets = ", ".join(
        f"{f} = excluded.{f}" for f in (*_TIMING_TIME_FIELDS, "is_closed")
    )
    return await database.fetchrow(
        f"""
        insert into facility_timings
            (facility_id, day_of_week, {', '.join(_TIMING_TIME_FIELDS)}, is_closed,
             is_test_data, is_demo, environment, created_by_seed)
        values ($1, $2, {time_ph}, {closed_ph}, true, false, 'dev', false)
        on conflict (facility_id, day_of_week) do update set {update_sets}
        returning {_TIMING_COLS}
        """,
        *values,
    )


# --- blackout dates --------------------------------------------------------
async def list_blackout(facility_id: str) -> list[dict]:
    return await database.fetch(
        "select id, facility_id, blackout_date, reason, created_at "
        "from facility_blackout_dates where facility_id = $1 order by blackout_date asc",
        facility_id,
    )


async def add_blackout(facility_id: str, blackout_date, reason: str | None = None) -> dict | None:
    return await database.fetchrow(
        """
        insert into facility_blackout_dates
            (facility_id, blackout_date, reason, is_test_data, is_demo, environment, created_by_seed)
        values ($1, $2::text::date, $3, true, false, 'dev', false)
        on conflict (facility_id, blackout_date) do update set reason = excluded.reason
        returning id, facility_id, blackout_date, reason, created_at
        """,
        facility_id, str(blackout_date), reason,
    )


async def remove_blackout(facility_id: str, blackout_id: str) -> bool:
    result = await database.execute(
        "delete from facility_blackout_dates where id = $1 and facility_id = $2",
        blackout_id, facility_id,
    )
    return result.upper().startswith("DELETE") and not result.endswith("0")


# --- team members ----------------------------------------------------------
_TEAM_COLS = (
    "id, facility_id, name, role, phone_masked, vehicle_type, responsibilities, "
    "status, last_activity_at, created_at, updated_at"
)


async def list_team(facility_id: str) -> list[dict]:
    """Team members — full phone_e164 is NEVER returned (masked only)."""
    return await database.fetch(
        f"select {_TEAM_COLS} from facility_team_members where facility_id = $1 "
        "order by created_at asc",
        facility_id,
    )


async def add_member(
    facility_id: str,
    *,
    name: str,
    role: str = "facility_staff",
    phone_e164: str | None = None,
    vehicle_type: str | None = None,
    responsibilities: str | None = None,
    status: str = "active",
) -> dict | None:
    return await database.fetchrow(
        f"""
        insert into facility_team_members
            (facility_id, name, role, phone_e164, phone_masked, vehicle_type,
             responsibilities, status, is_test_data, is_demo, environment, created_by_seed)
        values ($1, $2, $3, $4, $5, $6, $7, $8, true, false, 'dev', false)
        returning {_TEAM_COLS}
        """,
        facility_id, name, role, phone_e164,
        mask_phone(phone_e164) if phone_e164 else None,
        vehicle_type, responsibilities, status,
    )


async def update_member(
    facility_id: str,
    member_id: str,
    *,
    name: str | None = None,
    role: str | None = None,
    phone_e164: str | None = None,
    vehicle_type: str | None = None,
    responsibilities: str | None = None,
    status: str | None = None,
) -> dict | None:
    sets: list[str] = []
    params: list = [member_id, facility_id]

    def st(col, val):
        params.append(val)
        sets.append(f"{col} = ${len(params)}")

    if name is not None:
        st("name", name)
    if role is not None:
        st("role", role)
    if phone_e164 is not None:
        st("phone_e164", phone_e164)
        st("phone_masked", mask_phone(phone_e164))
    if vehicle_type is not None:
        st("vehicle_type", vehicle_type)
    if responsibilities is not None:
        st("responsibilities", responsibilities)
    if status is not None:
        st("status", status)
    if not sets:
        return await database.fetchrow(
            f"select {_TEAM_COLS} from facility_team_members where id = $1 and facility_id = $2",
            member_id, facility_id,
        )
    return await database.fetchrow(
        f"update facility_team_members set {', '.join(sets)} "
        f"where id = $1 and facility_id = $2 returning {_TEAM_COLS}",
        *params,
    )


# --- price-change requests + agreed-price view -----------------------------
_PRICE_REQ_COLS = (
    "id, facility_id, item_code, item_label, unit_type, current_price, "
    "requested_price, reason, status, decided_by, decision_note, created_at, "
    "updated_at, decided_at"
)


async def list_price_requests(facility_id: str) -> list[dict]:
    return await database.fetch(
        f"select {_PRICE_REQ_COLS} from facility_price_change_requests "
        "where facility_id = $1 order by created_at desc",
        facility_id,
    )


async def create_price_request(
    facility_id: str,
    *,
    item_code: str | None = None,
    item_label: str | None = None,
    unit_type: str | None = None,
    current_price=None,
    requested_price=None,
    reason: str | None = None,
    requested_by_user_id: str | None = None,
) -> dict | None:
    return await database.fetchrow(
        f"""
        insert into facility_price_change_requests
            (facility_id, item_code, item_label, unit_type, current_price,
             requested_price, reason, status, requested_by_user_id,
             is_test_data, is_demo, environment, created_by_seed)
        values ($1, $2, $3, $4, $5, $6, $7, 'pending', $8, true, false, 'dev', false)
        returning {_PRICE_REQ_COLS}
        """,
        facility_id, item_code, item_label, unit_type, current_price,
        requested_price, reason, requested_by_user_id,
    )


async def get_prices(facility_id: str) -> dict:
    """The catalogue prices the facility can VIEW. The facility-specific rate is
    not set yet, so we surface the published catalogue price + a note. Reuses the
    shared catalogue_repo so the facility sees exactly the agreed price list."""
    items = await catalogue_repo.list_items()
    priced = [
        {
            "item_code": i.get("item_code"),
            "name": i.get("canonical_name") or i.get("display_name"),
            "category": i.get("category_name"),
            "unit": i.get("pricing_unit"),
            "current_price": i.get("current_price"),
            "currency": i.get("currency") or "AED",
            "is_starting_price": bool(i.get("is_starting_price")),
        }
        for i in items
    ]
    return {
        "items": priced,
        "note": (
            "Prices shown are the published Laundry Khalas catalogue prices. A "
            "facility-specific payable rate is not configured yet — to propose a "
            "change, submit a price-change request for internal review."
        ),
    }
