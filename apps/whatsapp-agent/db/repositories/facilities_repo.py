"""Facility (laundry partner) profile + overview reads against the dev/test
Supabase schema.

A facility is the partner cleaning site the Facility Dashboard is scoped to. All
reads here are already scoped by ``facility_id`` (resolved by
``api/deps.require_facility_scope``); the profile never exposes customer PII.
"""
from __future__ import annotations

import uuid

from db import database

# Partner-safe columns. quality_score, payout_rate (internal rates), created_by/
# updated_by and market/country are deliberately absent — the partner never sees
# them (privacy firewall + internal-rate/quality isolation, CLAUDE.md §7).
_PROFILE_COLS = (
    "id, code, name, full_address, area, city, emirate, latitude, longitude, "
    "service_radius_km, capacity_daily, capacity_unit, accepts_orders, "
    "operating_status, is_active, onboarding_source, contact_area, notes, "
    "created_at, updated_at"
)
# Internal (admin/ops) columns — includes the protected fields.
_ADMIN_COLS = _PROFILE_COLS + ", quality_score, payout_rate, market, country, created_by, updated_by"


def _num(v):
    return None if v is None else float(v)


def to_profile(row: dict) -> dict:
    """Facility profile (non-PII, PARTNER-SAFE). ``quality_score`` and internal
    rates (``payout_rate``/facility_rates) are intentionally NOT exposed — they
    are internal-only (CLAUDE.md §7)."""
    return {
        "id": str(row["id"]),
        "code": row.get("code"),
        "name": row.get("name"),
        "full_address": row.get("full_address"),
        "area": row.get("area"),
        "city": row.get("city"),
        "emirate": row.get("emirate"),
        "latitude": _num(row.get("latitude")),
        "longitude": _num(row.get("longitude")),
        "service_radius_km": _num(row.get("service_radius_km")),
        "capacity_daily": row.get("capacity_daily"),
        "capacity_unit": row.get("capacity_unit"),
        "accepts_orders": bool(row.get("accepts_orders")),
        "operating_status": row.get("operating_status"),
        "is_active": bool(row.get("is_active")),
        "onboarding_source": row.get("onboarding_source"),
        "contact_area": row.get("contact_area"),
        "notes": row.get("notes"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        # Optional list-query extras (present only on list_filtered rows).
        **({"service_codes": [c for c in row["service_codes"] if c]}
           if row.get("service_codes") is not None else {}),
        **({"open_days": row.get("open_days")} if "open_days" in row else {}),
    }


def to_admin_profile(row: dict) -> dict:
    """Internal facility profile — INCLUDES quality_score. Never return this from a
    partner-facing endpoint."""
    profile = to_profile(row)
    profile.update({
        "quality_score": _num(row.get("quality_score")),
        "market": row.get("market"),
        "country": row.get("country"),
        "created_by": str(row["created_by"]) if row.get("created_by") else None,
        "updated_by": str(row["updated_by"]) if row.get("updated_by") else None,
    })
    return profile


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
        """
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


# ---------------------------------------------------------------------------
# Management writes (create / update / status) + admin reads
# ---------------------------------------------------------------------------
# Columns a management caller may write. quality_score/payout_rate are here but
# are gated to internal callers at the API/schema layer (partner schemas omit
# them and reject them with extra="forbid").
_WRITABLE = frozenset({
    "name", "full_address", "area", "city", "emirate", "latitude", "longitude",
    "service_radius_km", "capacity_daily", "capacity_unit", "operating_status",
    "quality_score", "market", "country", "accepts_orders", "contact_area",
    "notes", "onboarding_source", "is_active", "payout_rate",
})
# numeric(*) columns — asyncpg wants Decimal for numeric, so we pass the value as
# text and cast (mirrors the ::text::time pattern in facility_settings_repo).
_TEXT_NUMERIC = frozenset({"latitude", "longitude", "service_radius_km",
                           "quality_score", "payout_rate"})


def _placeholder(col: str, idx: int) -> str:
    return f"${idx}::text::numeric" if col in _TEXT_NUMERIC else f"${idx}"


def _coerce(col, val):
    if val is None:
        return None
    return str(val) if col in _TEXT_NUMERIC else val


def _gen_code(name: str | None) -> str:
    return f"FAC-{uuid.uuid4().hex[:6].upper()}"


async def create(fields: dict, *, actor_id: str | None = None) -> dict | None:
    """Insert a facility. ``fields`` is filtered to writable columns; a stable
    ``code`` is generated when not supplied. Returns the internal admin profile."""
    data = {k: v for k, v in fields.items() if k in _WRITABLE and v is not None}
    data.setdefault("onboarding_source", "admin_dashboard")
    code = fields.get("code") or _gen_code(data.get("name"))
    if actor_id:
        data["created_by"] = actor_id
        data["updated_by"] = actor_id

    cols = ["code"]
    vals = ["$1"]
    params: list = [code]
    for col, val in data.items():
        params.append(_coerce(col, val))
        cols.append(col)
        vals.append(_placeholder(col, len(params)))
    row = await database.fetchrow(
        f"insert into facilities ({', '.join(cols)}) values ({', '.join(vals)}) returning id",
        *params,
    )
    return await get_admin(str(row["id"])) if row else None


async def update(facility_id: str, patch: dict, *, actor_id: str | None = None) -> dict | None:
    """Patch writable columns on a facility. Returns the internal admin profile."""
    data = {k: v for k, v in patch.items() if k in _WRITABLE and v is not None}
    if actor_id:
        data["updated_by"] = actor_id
    if not data:
        return await get_admin(facility_id)
    sets: list[str] = []
    params: list = [facility_id]
    for col, val in data.items():
        params.append(_coerce(col, val))
        sets.append(f"{col} = {_placeholder(col, len(params))}")
    sets.append("updated_at = now()")
    row = await database.fetchrow(
        f"update facilities set {', '.join(sets)} where id = $1 returning id", *params,
    )
    return await get_admin(facility_id) if row else None


async def set_status(facility_id: str, status: str, *, actor_id: str | None = None) -> dict | None:
    return await update(facility_id, {"operating_status": status}, actor_id=actor_id)


async def get_admin(facility_id: str) -> dict | None:
    row = await database.fetchrow(
        f"select {_ADMIN_COLS} from facilities where id = $1", facility_id
    )
    return to_admin_profile(row) if row else None


async def list_filtered(
    *, search: str | None = None, status: str | None = None,
    emirate: str | None = None, service_code: str | None = None,
) -> list[dict]:
    """Internal facility list with optional filters. Each row carries the accepted
    ``service_codes`` array + ``open_days`` count for the card summary."""
    where = ["1=1"]
    params: list = []

    def add(clause: str, val):
        params.append(val)
        where.append(clause.replace("$?", f"${len(params)}"))

    if search:
        add("(f.name ilike '%'||$?||'%' or f.code ilike '%'||$?||'%' "
            "or f.area ilike '%'||$?||'%' or f.city ilike '%'||$?||'%')", search)
    if status:
        add("f.operating_status = $?", status)
    if emirate:
        add("f.emirate = $?", emirate)
    if service_code:
        params.append(service_code)
        where.append(
            f"exists (select 1 from facility_services fs where fs.facility_id = f.id "
            f"and fs.service_code = ${len(params)} and fs.offered = true)"
        )
    rows = await database.fetch(
        f"""
        select {', '.join('f.' + c.strip() for c in _ADMIN_COLS.split(','))},
          (select array_agg(fs.service_code order by fs.service_code)
             from facility_services fs
             where fs.facility_id = f.id and fs.offered = true) as service_codes,
          (select count(*) from facility_timings ft
             where ft.facility_id = f.id and ft.is_closed = false) as open_days
        from facilities f
        where {' and '.join(where)}
        order by f.created_at desc
        """,
        *params,
    )
    return [to_admin_profile(r) for r in rows]


async def status_counts() -> dict:
    """Counts per operating_status for the management summary cards."""
    rows = await database.fetch(
        "select operating_status, count(*) as c from facilities group by operating_status"
    )
    by_status = {r["operating_status"]: r["c"] for r in rows}
    return {
        "total": sum(by_status.values()),
        "open": by_status.get("open", 0),
        "busy": by_status.get("busy", 0),
        "paused": by_status.get("paused", 0),
        "closed": by_status.get("closed", 0),
    }


# --- accepted services (category-level, validated at the service layer) -----
async def get_services(facility_id: str) -> list[str]:
    rows = await database.fetch(
        "select service_code from facility_services "
        "where facility_id = $1 and offered = true order by service_code",
        facility_id,
    )
    return [r["service_code"] for r in rows]


async def set_services(facility_id: str, codes: list[str]) -> list[str]:
    """Replace the facility's accepted service set. Codes not in ``codes`` are
    marked offered=false (kept for history); codes in the list are upserted
    offered=true. Callers must validate codes against the catalogue first."""
    await database.execute(
        "update facility_services set offered = false where facility_id = $1", facility_id
    )
    for code in codes:
        await database.execute(
            "insert into facility_services (facility_id, service_code, offered) "
            "values ($1, $2, true) "
            "on conflict (facility_id, service_code) do update set offered = true",
            facility_id, code,
        )
    return await get_services(facility_id)
