"""Quality-metrics aggregates (Supabase dev/test schema).

Deterministic SQL rollups feeding ``services/metrics.build_quality_report``.
Consumer conversion EXCLUDES B2B leads (``customers.is_b2b = false``) and demo
rows (unless ENABLE_DEMO_DATA). Read-only. Returns an all-zero report outside
supabase mode so the ops dashboard degrades gracefully.
"""
from __future__ import annotations

from db import database
from services import metrics
from settings import get_settings


def _include_demo() -> bool:
    return get_settings().enable_demo_data


async def _consumer(inc: bool) -> dict:
    row = await database.fetchrow(
        """
        with cust as (
          select c.id, c.funnel_stage,
            (select count(*) from orders o
               where o.customer_id = c.id and o.confirmed_at is not null
                 and (o.is_demo = false or $1)) as confirmed,
            (select coalesce(sum(coalesce(o.estimated_total, o.amount, 0)), 0) from orders o
               where o.customer_id = c.id and o.confirmed_at is not null
                 and (o.is_demo = false or $1)) as revenue,
            (select bool_or(o.status = 'draft') from orders o where o.customer_id = c.id) as has_draft
          from customers c
          where c.is_b2b = false and (c.is_demo = false or $1)
        )
        select
          count(*)                                             as total_customers,
          count(*) filter (where confirmed >= 1)               as customers_with_confirmed,
          count(*) filter (where confirmed >= 2)               as repeat_customers,
          count(*) filter (where coalesce(has_draft, false))   as booking_started,
          count(*) filter (where funnel_stage = 'PRICE_ENQUIRY') as price_enquiry_customers,
          coalesce(sum(confirmed), 0)                          as confirmed_orders,
          coalesce(sum(revenue), 0)                            as confirmed_revenue
        from cust
        """,
        inc,
    )
    return dict(row) if row else {}


async def _escalations() -> dict:
    row = await database.fetchrow(
        """
        select
          (select count(*) from conversations)                                    as total_conversations,
          (select count(distinct conversation_id) from agent_flags)               as flagged_conversations,
          (select count(*) from complaints where status in ('open','in_review'))  as open_complaints,
          (select count(*) from pending_tasks where status in ('open','in_progress')) as pending_tasks_open,
          (select count(*) from pending_tasks
             where status in ('open','in_progress') and escalated = false
               and due_at is not null and due_at < now())                         as pending_tasks_overdue
        """
    )
    return dict(row) if row else {}


async def _by_service(inc: bool) -> list[dict]:
    rows = await database.fetch(
        """
        select coalesce(catalogue_category_name, service, 'Unknown') as service,
               count(*) as confirmed,
               coalesce(sum(coalesce(estimated_total, amount, 0)), 0) as revenue
        from orders
        where confirmed_at is not null and (is_demo = false or $1)
        group by 1 order by confirmed desc, service asc
        """,
        inc,
    )
    return [{"service": r["service"], "confirmed": r["confirmed"],
             "revenue_aed": round(float(r["revenue"] or 0), 2)} for r in rows]


async def _by_market(inc: bool) -> list[dict]:
    rows = await database.fetch(
        """
        select coalesce(c.market, 'unknown') as market, count(*) as confirmed
        from orders o join customers c on c.id = o.customer_id
        where o.confirmed_at is not null and c.is_b2b = false and (o.is_demo = false or $1)
        group by 1 order by confirmed desc
        """,
        inc,
    )
    return [{"market": r["market"], "confirmed": r["confirmed"]} for r in rows]


async def _by_segment(inc: bool) -> list[dict]:
    rows = await database.fetch(
        """
        select coalesce(lifecycle_stage, 'unknown') as lifecycle_stage, count(*) as count
        from customers where (is_demo = false or $1)
        group by 1 order by count desc
        """,
        inc,
    )
    return [{"lifecycle_stage": r["lifecycle_stage"], "count": r["count"]} for r in rows]


async def _b2b() -> dict:
    n = await database.fetchval(
        "select count(*) from b2b_leads where status not in ('won','lost')"
    )
    return {"open_leads": n or 0}


async def quality_report() -> dict:
    """The full deterministic quality report. All-zero outside supabase mode."""
    if not database.is_supabase_mode():
        return metrics.build_quality_report({})
    inc = _include_demo()
    raw = {
        "consumer": await _consumer(inc),
        "escalations": await _escalations(),
        "by_service": await _by_service(inc),
        "by_market": await _by_market(inc),
        "by_segment": await _by_segment(inc),
        "b2b": await _b2b(),
    }
    return metrics.build_quality_report(raw)
