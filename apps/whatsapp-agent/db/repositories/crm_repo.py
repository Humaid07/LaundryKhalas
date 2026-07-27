"""CRM aggregate gathering + deterministic recompute (Supabase dev/test schema).

Reads a customer's orders + escalation flags to build ``CustomerFacts``, runs the
pure ``services/crm_segments`` engine, and persists the result (lifecycle_stage,
funnel_stage, segments + aggregates) onto the ``customers`` row as a recomputation
CACHE. Everything here is deterministic backend logic — the LLM never writes these.

``recompute_for_customer`` is best-effort and NEVER raises into a caller: a CRM
recompute must not break a booking confirmation or an escalation. It is invoked at
deterministic lifecycle points (booking confirmed, complaint/escalation raised) and
can also be run in bulk by a maintenance script.
"""
from __future__ import annotations

import json
from decimal import Decimal

import structlog

from db import database
from services import crm_segments
from services.crm_segments import CustomerFacts

logger = structlog.get_logger()

# Flag types that mean an OPEN customer complaint (vs. a plain B2B/other flag).
_COMPLAINT_FLAG_TYPES = (
    "complaint", "refund_request", "damaged_item", "missing_item",
    "late_delivery", "payment_issue",
)


async def gather_facts(customer_id: str) -> CustomerFacts:
    """Build a customer's CRM facts from orders + flags. All queries scoped to the
    one customer_id. A 'confirmed' order is one with a confirmed_at timestamp."""
    order_row = await database.fetchrow(
        """
        select
          count(*) filter (where confirmed_at is not null)              as confirmed_count,
          coalesce(sum(coalesce(estimated_total, amount, 0))
                   filter (where confirmed_at is not null), 0)          as lifetime_value,
          count(*) filter (where discount_requested is true)            as discount_requests,
          bool_or(coalesce(requires_manual_quote, false))               as has_bespoke,
          bool_or(status = 'draft')                                     as has_active_draft,
          max(created_at)                                               as last_order_at
        from orders
        where customer_id = $1
        """,
        customer_id,
    )

    # Open complaint / B2B via agent_flags joined through the customer's conversations.
    flag_row = await database.fetchrow(
        """
        select
          bool_or(f.flag_type = any($2::text[]) and f.status = 'open') as has_open_complaint,
          bool_or(f.flag_type = 'b2b_lead')                            as is_b2b
        from agent_flags f
        join conversations c on c.id = f.conversation_id
        where c.customer_id = $1
        """,
        customer_id, list(_COMPLAINT_FLAG_TYPES),
    )

    activity_row = await database.fetchrow(
        """
        select
          max(last_message_at)                                          as last_activity_at,
          bool_or(true)                                                 as has_any
        from conversations
        where customer_id = $1
        """,
        customer_id,
    )

    last_activity = activity_row["last_activity_at"] if activity_row else None
    days_since = None
    if last_activity is not None:
        days_row = await database.fetchrow(
            "select greatest(0, extract(day from (now() - $1))::int) as d", last_activity
        )
        days_since = days_row["d"] if days_row else None

    return CustomerFacts(
        confirmed_order_count=int(order_row["confirmed_count"] or 0) if order_row else 0,
        lifetime_value=Decimal(str(order_row["lifetime_value"] or 0)) if order_row else Decimal("0"),
        discount_request_count=int(order_row["discount_requests"] or 0) if order_row else 0,
        price_enquiry_count=0,  # fed by the price-enquiry funnel slice (column default 0)
        has_bespoke=bool(order_row["has_bespoke"]) if order_row else False,
        has_active_draft=bool(order_row["has_active_draft"]) if order_row else False,
        has_open_complaint=bool(flag_row["has_open_complaint"]) if flag_row else False,
        is_b2b=bool(flag_row["is_b2b"]) if flag_row else False,
        has_any_activity=bool(activity_row["has_any"]) if activity_row else False,
        days_since_activity=days_since,
    )


async def recompute_for_customer(customer_id: str) -> dict | None:
    """Gather facts → evaluate the deterministic engine → persist onto customers.
    Best-effort: logs and returns None on any error, never raising into the caller."""
    try:
        facts = await gather_facts(customer_id)
        result = crm_segments.evaluate(facts)
        # last_order_at / last_activity_at come from correlated subqueries so the
        # timestamptz values never round-trip through Python (kept as pure cache).
        row = await database.fetchrow(
            """
            update customers c set
              lifecycle_stage        = $2,
              funnel_stage           = $3,
              segments               = $4::jsonb,
              confirmed_order_count  = $5,
              lifetime_value         = $6,
              discount_request_count = $7,
              has_open_complaint     = $8,
              is_b2b                 = $9,
              last_order_at          = (select max(created_at) from orders where customer_id = $1),
              last_activity_at       = (select max(last_message_at) from conversations where customer_id = $1),
              segments_computed_at   = now()
            where c.id = $1
            returning id, lifecycle_stage, funnel_stage, segments
            """,
            customer_id,
            result.lifecycle_stage,
            result.funnel_stage,
            json.dumps(result.segments),
            facts.confirmed_order_count,
            facts.lifetime_value,
            facts.discount_request_count,
            facts.has_open_complaint,
            facts.is_b2b,
        )
        if row:
            logger.info("crm_recomputed", customer=customer_id,
                        lifecycle=result.lifecycle_stage, funnel=result.funnel_stage,
                        segments=result.segments)
        return result.as_dict() if row else None
    except Exception as exc:  # noqa: BLE001 - CRM recompute never breaks the caller
        logger.warning("crm_recompute_error", customer=customer_id, error=str(exc))
        return None


async def get_crm_profile(customer_id: str) -> dict | None:
    """Read the persisted CRM cache for a customer (for the ops dashboard)."""
    row = await database.fetchrow(
        """
        select id, display_name, market, lifecycle_stage, funnel_stage, segments,
               confirmed_order_count, lifetime_value, discount_request_count,
               price_enquiry_count, has_open_complaint, is_b2b,
               last_order_at, last_activity_at, segments_computed_at
        from customers where id = $1
        """,
        customer_id,
    )
    if not row:
        return None
    d = dict(row)
    d["id"] = str(d["id"])
    d["lifetime_value"] = float(d["lifetime_value"]) if d["lifetime_value"] is not None else 0.0
    # asyncpg returns jsonb as a raw string — decode to a list for the dashboard.
    if isinstance(d.get("segments"), str):
        d["segments"] = json.loads(d["segments"])
    return d
