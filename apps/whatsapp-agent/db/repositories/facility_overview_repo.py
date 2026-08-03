"""Fleet-level facility metrics for the internal Facilities → Overview page.

Every number here is derived from real rows (facilities / orders / facility_issues
/ facility_services). Where a facility has no backing data (e.g. no completed
orders, or no capacity set) the metric is returned as ``None`` so the UI can show
"no data yet" rather than an invented value (CLAUDE.md §7/§9).

All order counts are scoped by ``orders.facility_id``. Filters (city/emirate/
status/service) apply at the FACILITY level; the period (``days``) applies to the
time-boxed order/issue metrics via ``completed_at`` / ``created_at``.
"""
from __future__ import annotations

from db import database

# Order-status lanes (mirror facility_orders_repo / facilities_repo).
_IN_PROGRESS = ("active", "pickup_scheduled", "picked_up", "in_cleaning",
                "ready_for_delivery", "out_for_delivery")
_ATTENTION = ("support_required", "cancellation_requested", "pickup_change_requested")


def _sql_list(values: tuple[str, ...]) -> str:
    """Render a fixed status tuple as an inline SQL string list (constants, not
    user input — safe to inline; keeps the parameter numbering simple)."""
    return ", ".join("'" + v.replace("'", "''") + "'" for v in values)


def _facility_where(filters: dict) -> tuple[str, list]:
    """Build the facility-level WHERE clause + params (city/emirate/status/service)."""
    where = ["1=1"]
    params: list = []

    def add(clause: str, val):
        params.append(val)
        where.append(clause.replace("$?", f"${len(params)}"))

    if filters.get("status"):
        add("f.operating_status = $?", filters["status"])
    if filters.get("city"):
        add("lower(f.city) = lower($?)", filters["city"])
    if filters.get("emirate"):
        add("f.emirate = $?", filters["emirate"])
    if filters.get("service"):
        params.append(filters["service"])
        where.append(
            f"exists (select 1 from facility_services fs where fs.facility_id = f.id "
            f"and fs.service_code = ${len(params)} and fs.offered = true)"
        )
    return " and ".join(where), params


async def facility_metrics(filters: dict) -> list[dict]:
    """Per-facility metric rows for every facility matching the filters."""
    where, params = _facility_where(filters)
    # Period param ($N) reused across the time-boxed sub-selects. None → all-time.
    params.append(filters.get("days"))
    d = f"${len(params)}::int"
    inprog = _sql_list(_IN_PROGRESS)
    attn = _sql_list(_ATTENTION)

    rows = await database.fetch(
        f"""
        select
          f.id, f.name, f.code, f.city, f.area, f.emirate,
          f.operating_status, f.is_active, f.capacity_daily, f.quality_score,
          (select count(*) from orders o where o.facility_id = f.id
             and o.status in ({inprog})) as in_progress,
          (select count(*) from orders o where o.facility_id = f.id
             and o.status in ({attn})) as attention_orders,
          (select count(*) from orders o where o.facility_id = f.id
             and o.status in ({inprog})
             and o.estimated_delivery_end_at is not null
             and o.estimated_delivery_end_at < now()) as delayed,
          (select count(*) from orders o where o.facility_id = f.id
             and o.status = 'completed'
             and ({d} is null or o.completed_at >= now() - ({d} * interval '1 day'))) as completed_period,
          (select count(*) from orders o where o.facility_id = f.id
             and o.status = 'completed') as completed_all,
          (select count(*) from orders o where o.facility_id = f.id
             and o.status <> 'draft') as total_all,
          (select count(*) from facility_issues fi where fi.facility_id = f.id
             and fi.status not in ('resolved','closed')) as open_issues,
          (select count(*) from facility_issues fi where fi.facility_id = f.id
             and ({d} is null or fi.created_at >= now() - ({d} * interval '1 day'))) as issues_period
        from facilities f
        where {where}
        order by f.name asc
        """,
        *params,
    )
    return [
        {
            "id": str(r["id"]),
            "name": r["name"],
            "code": r["code"],
            "city": r["city"],
            "area": r["area"],
            "emirate": r["emirate"],
            "operating_status": r["operating_status"],
            "is_active": bool(r["is_active"]),
            "capacity_daily": r["capacity_daily"],
            "quality_score": None if r["quality_score"] is None else float(r["quality_score"]),
            "in_progress": r["in_progress"] or 0,
            "attention_orders": r["attention_orders"] or 0,
            "delayed": r["delayed"] or 0,
            "completed_period": r["completed_period"] or 0,
            "completed_all": r["completed_all"] or 0,
            "total_all": r["total_all"] or 0,
            "open_issues": r["open_issues"] or 0,
            "issues_period": r["issues_period"] or 0,
        }
        for r in rows
    ]


async def avg_completion_seconds(filters: dict) -> float | None:
    """Fleet-wide average completed-order turnaround (confirmed → completed), in
    seconds, over the filtered facilities + period. ``None`` when there are no
    completed orders with both timestamps (honest 'no data yet')."""
    where, params = _facility_where(filters)
    params.append(filters.get("days"))
    d = f"${len(params)}::int"
    val = await database.fetchval(
        f"""
        select avg(extract(epoch from (o.completed_at - o.confirmed_at)))
        from orders o
        join facilities f on f.id = o.facility_id
        where o.status = 'completed'
          and o.completed_at is not null and o.confirmed_at is not null
          and o.completed_at >= o.confirmed_at
          and ({d} is null or o.completed_at >= now() - ({d} * interval '1 day'))
          and {where}
        """,
        *params,
    )
    return None if val is None else float(val)


async def service_coverage(filters: dict) -> dict[str, int]:
    """Count of facilities offering each service_code, over the filtered facilities.
    The ``service`` filter is intentionally ignored here (coverage should show ALL
    services, including gaps). Returns {service_code: facility_count}."""
    coverage_filters = {k: v for k, v in filters.items() if k != "service"}
    where, params = _facility_where(coverage_filters)
    rows = await database.fetch(
        f"""
        select fs.service_code, count(distinct fs.facility_id) as facility_count
        from facility_services fs
        join facilities f on f.id = fs.facility_id
        where fs.offered = true and {where}
        group by fs.service_code
        """,
        *params,
    )
    return {r["service_code"]: r["facility_count"] for r in rows}
