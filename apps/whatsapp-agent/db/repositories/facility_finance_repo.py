"""Facility-SCOPED finance reads against the dev/test Supabase schema.

Every query filters ``o.facility_id = $1``. This surfaces CUSTOMER order value
only ("Completed Service Value") — the partner PAYOUT rate is a deferred
placeholder (``facilities.payout_rate`` is null), so payout is always reported as
``pending_rate`` with a null amount. No payout is invented (CLAUDE.md §8).

Revenue-eligible = status NOT IN ('draft','cancelled','abandoned') and the row is
visible under the demo rule. All money is summed/rounded via ``services/money``.
"""
from __future__ import annotations

from services import money
from settings import get_settings
from db import database

_INELIGIBLE = ("draft", "cancelled", "abandoned")
_GRANULARITY = {"day": "day", "week": "week", "month": "month"}


def _include_demo() -> bool:
    return get_settings().enable_demo_data


def _eligible_sql(param_start: int) -> tuple[str, list]:
    """Revenue-eligibility WHERE fragment + demo param (bind index param_start)."""
    return (
        f"o.status <> all(${param_start}::text[]) and (o.is_demo = false or ${param_start + 1})",
        [list(_INELIGIBLE), _include_demo()],
    )


async def summary(facility_id: str, date_from=None, date_to=None) -> dict:
    """Revenue total / order count / average order value over the range."""
    elig, elig_params = _eligible_sql(2)
    params: list = [facility_id, *elig_params]
    conds = ["o.facility_id = $1", elig]
    if date_from is not None:
        params.append(date_from)
        conds.append(f"coalesce(o.confirmed_at, o.created_at) >= ${len(params)}")
    if date_to is not None:
        params.append(date_to)
        conds.append(f"coalesce(o.confirmed_at, o.created_at) < ${len(params)}")
    row = await database.fetchrow(
        "select count(*) as order_count, "
        "coalesce(sum(coalesce(o.estimated_total, o.amount)), 0) as revenue_total "
        f"from orders o where {' and '.join(conds)}",
        *params,
    )
    count = row["order_count"] if row else 0
    revenue = money.round_money(row["revenue_total"] if row else 0)
    avg = money.round_money(revenue / count) if count else money.round_money(0)
    return {
        "currency": "AED",
        "order_count": count,
        "revenue_total": float(revenue),
        "revenue_total_display": f"AED {money.format_money(revenue)}",
        "average_order_value": float(avg),
        "average_order_value_display": f"AED {money.format_money(avg)}",
        # Partner payout deferred — no invented amount (CLAUDE.md §8).
        "payout_status": "pending_rate",
        "payout_amount": None,
        "date_from": str(date_from) if date_from is not None else None,
        "date_to": str(date_to) if date_to is not None else None,
    }


async def revenue_timeseries(facility_id: str, granularity="day", date_from=None, date_to=None) -> list[dict]:
    """Revenue grouped by day|week|month on COALESCE(confirmed_at, created_at)."""
    trunc = _GRANULARITY.get((granularity or "day").lower(), "day")
    elig, elig_params = _eligible_sql(2)
    params: list = [facility_id, *elig_params]
    conds = ["o.facility_id = $1", elig]
    if date_from is not None:
        params.append(date_from)
        conds.append(f"coalesce(o.confirmed_at, o.created_at) >= ${len(params)}")
    if date_to is not None:
        params.append(date_to)
        conds.append(f"coalesce(o.confirmed_at, o.created_at) < ${len(params)}")
    rows = await database.fetch(
        f"select date_trunc('{trunc}', coalesce(o.confirmed_at, o.created_at)) as period, "
        "count(*) as count, "
        "coalesce(sum(coalesce(o.estimated_total, o.amount)), 0) as value "
        f"from orders o where {' and '.join(conds)} "
        "group by 1 order by 1 asc",
        *params,
    )
    return [
        {
            "period": str(r["period"]),
            "count": r["count"],
            "value": float(money.round_money(r["value"])),
        }
        for r in rows
    ]


async def service_mix(facility_id: str, date_from=None, date_to=None) -> list[dict]:
    """Aggregate order value by service category. Prefers the catalogue category
    (via line_items.item_code → service_items → service_categories); falls back to
    the order's snapshot catalogue_category_name / service_display_name."""
    elig, elig_params = _eligible_sql(2)
    params: list = [facility_id, *elig_params]
    conds = ["o.facility_id = $1", elig]
    if date_from is not None:
        params.append(date_from)
        conds.append(f"coalesce(o.confirmed_at, o.created_at) >= ${len(params)}")
    if date_to is not None:
        params.append(date_to)
        conds.append(f"coalesce(o.confirmed_at, o.created_at) < ${len(params)}")
    rows = await database.fetch(
        f"""
        select
          coalesce(sc.name, o.catalogue_category_name, o.service_display_name, o.service, 'Other') as category,
          count(distinct o.id) as count,
          coalesce(sum(coalesce(o.estimated_total, o.amount)), 0) as value
        from orders o
        left join lateral (
          select li->>'item_code' as item_code
          from jsonb_array_elements(coalesce(o.line_items, '[]'::jsonb)) li
          limit 1
        ) first_li on true
        left join service_items si on si.item_code = first_li.item_code
        left join service_categories sc on sc.id = si.category_id
        where {' and '.join(conds)}
        group by 1
        order by value desc
        """,
        *params,
    )
    return [
        {"category": r["category"], "count": r["count"], "value": float(money.round_money(r["value"]))}
        for r in rows
    ]
