"""Facility-SCOPED order reads against the dev/test Supabase schema.

EVERY query in this module filters ``o.facility_id = $1`` — a facility can only
ever see its own orders. The service role bypasses RLS, so this application-level
filter (plus ``api/deps.require_facility_scope``) is the isolation boundary; a
mismatched facility returns None/[] rather than another facility's data.

The row → dict serializer ``to_facility_read`` is PII-SAFE: it exposes only
order-scoped, operational fields (status, service/items, area/city, cleaning
instructions, SLA, times, order value, driver label, customer FIRST name). It
NEVER returns the customer's full phone, email, full pickup address, payment
method, or private notes (CLAUDE.md §7).
"""
from __future__ import annotations

from services import order_store
from settings import get_settings
from db import database

# Bucket → status membership (facility operational lanes).
BUCKET_STATUSES: dict[str, tuple[str, ...]] = {
    "in": ("active", "pickup_scheduled", "picked_up", "in_cleaning"),
    "out": ("ready_for_delivery", "out_for_delivery"),
    "completed": ("completed",),
    "attention": ("support_required", "cancellation_requested", "pickup_change_requested"),
}
# Terminal / hidden statuses for the "upcoming" (non-terminal) lane.
_NON_TERMINAL_EXCLUDE = ("draft", "completed", "cancelled", "abandoned")


def _include_demo() -> bool:
    return get_settings().enable_demo_data


def _first_name(name: str | None) -> str:
    """Customer LABEL = first name only (privacy). Blank → 'Customer'."""
    if not name or not str(name).strip():
        return "Customer"
    return str(name).strip().split()[0]


def _item_breakdown(row: dict) -> list[dict]:
    """Operational item list: name + quantity only (no pricing leakage rules
    needed, but we keep it minimal). Falls back to the legacy ``items`` array."""
    out: list[dict] = []
    line_items = row.get("line_items") or []
    if isinstance(line_items, list) and line_items:
        for li in line_items:
            if not isinstance(li, dict):
                out.append({"name": str(li), "quantity": None})
                continue
            out.append({
                "name": li.get("name") or li.get("canonical_name") or li.get("item_code") or "Item",
                "quantity": li.get("quantity"),
                "measure": li.get("measure"),
            })
        return out
    items = row.get("items") or []
    if isinstance(items, str):
        items = [items]
    for it in items:
        if isinstance(it, dict):
            out.append({"name": it.get("item") or it.get("name") or "Item",
                        "quantity": it.get("quantity")})
        else:
            out.append({"name": str(it), "quantity": None})
    return out


def to_facility_read(row: dict) -> dict:
    """PII-SAFE facility view of an order row. Only order-scoped operational
    fields — never customer phone/email/full address/payment method/private
    notes (CLAUDE.md §7)."""
    status = row.get("status") or "active"
    total = row.get("estimated_total")
    if total is None:
        total = row.get("amount")
    return {
        "order_id": row.get("order_id"),
        "status": status,
        "status_label": order_store.status_label(status),
        "service": row.get("service_display_name") or row.get("service"),
        "service_id": row.get("service_id"),
        "category": row.get("catalogue_category_name"),
        "items": _item_breakdown(row),
        # Area/city only — NEVER the full pickup address.
        "area": row.get("pickup_area") or row.get("area"),
        "city": row.get("city"),
        "emirate": row.get("pickup_emirate"),
        # Operational / cleaning instruction (not customer PII).
        "instructions": row.get("pickup_instruction_text"),
        # SLA / turnaround.
        "turnaround_text": row.get("turnaround_text"),
        "estimated_delivery_text": row.get("estimated_delivery_text"),
        "express_eligible": bool(row.get("express_eligible")) if row.get("express_eligible") is not None else None,
        # Times.
        "pickup_date": (str(row["pickup_date"]) if row.get("pickup_date") else None),
        "pickup_time": row.get("pickup_slot"),
        "pickup_start_time": row.get("pickup_start_time"),
        "pickup_end_time": row.get("pickup_end_time"),
        "estimated_delivery_start_at": row.get("estimated_delivery_start_at"),
        "estimated_delivery_end_at": row.get("estimated_delivery_end_at"),
        # Facility order value (customer order value — partner payout is deferred).
        "order_value": float(total) if total is not None else None,
        "currency": "AED",
        # Non-PII labels.
        "driver": row.get("driver"),
        "customer_label": _first_name(row.get("customer_name")),
        "is_paid": bool(row.get("payment_status") in ("paid", "captured", "completed")),
        "open_issue_count": row.get("open_issue_count") or 0,
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "confirmed_at": row.get("confirmed_at"),
        "completed_at": row.get("completed_at"),
    }


def _bucket_where(bucket: str, next_param_index: int) -> tuple[str, list]:
    """Return (sql_condition, extra_params) for a bucket, using bind params
    starting at ``next_param_index`` ($1 is always facility_id)."""
    params: list = []

    def ph(v):
        params.append(v)
        return f"${next_param_index + len(params) - 1}"

    if bucket in ("in", "out", "completed"):
        return f"o.status = any({ph(list(BUCKET_STATUSES[bucket]))}::text[])", params
    if bucket == "attention":
        # exception status OR an OPEN facility issue linked to the order.
        cond = (
            f"(o.status = any({ph(list(BUCKET_STATUSES['attention']))}::text[]) "
            "or exists (select 1 from facility_issues fi "
            "where fi.order_id = o.id and fi.status not in ('resolved','closed')))"
        )
        return cond, params
    if bucket == "upcoming":
        cond = (
            f"o.status <> all({ph(list(_NON_TERMINAL_EXCLUDE))}::text[]) "
            "and o.pickup_date >= (now() at time zone 'Asia/Dubai')::date"
        )
        return cond, params
    # "all" — everything for the facility (no extra status filter).
    return "true", params


_SELECT_COLS = (
    "o.*, (select count(*) from facility_issues fi "
    "where fi.order_id = o.id and fi.status not in ('resolved','closed')) as open_issue_count"
)


async def list_bucket(
    facility_id: str,
    bucket: str = "all",
    *,
    date_from=None,
    date_to=None,
    service_id: str | None = None,
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    conds = ["o.facility_id = $1"]
    params: list = [facility_id]

    def ph(v):
        params.append(v)
        return f"${len(params)}"

    # Demo filtering (mirror orders_repo): hide is_demo rows unless enabled.
    conds.append(f"(o.is_demo = false or {ph(_include_demo())})")

    bucket_cond, bucket_params = _bucket_where(bucket, len(params) + 1)
    params.extend(bucket_params)
    if bucket_cond and bucket_cond != "true":
        conds.append(bucket_cond)

    if service_id:
        conds.append(f"o.service_id = {ph(service_id)}")
    if status:
        conds.append(f"o.status = {ph(status)}")
    if date_from is not None:
        conds.append(f"o.pickup_date >= {ph(date_from)}")
    if date_to is not None:
        conds.append(f"o.pickup_date <= {ph(date_to)}")

    limit_ph = ph(max(1, min(int(limit), 200)))
    offset_ph = ph(max(0, int(offset)))
    rows = await database.fetch(
        f"select {_SELECT_COLS} from orders o "
        f"where {' and '.join(conds)} "
        f"order by o.pickup_date asc nulls last, o.created_at desc "
        f"limit {limit_ph} offset {offset_ph}",
        *params,
    )
    return [to_facility_read(r) for r in rows]


async def get(facility_id: str, order_id: str) -> dict | None:
    """One order by UUID OR business order_id, SCOPED to the facility. Returns
    None when the order is not this facility's — the facility_id filter is the
    isolation guard, so another facility's order is indistinguishable from a
    non-existent one."""
    row = await database.fetchrow(
        f"select {_SELECT_COLS} from orders o "
        "where o.facility_id = $1 and ("
        "  o.id::text = $2 "
        "  or upper(replace(o.order_id,' ','')) = upper(replace($2,' ','')))",
        facility_id, order_id,
    )
    return to_facility_read(row) if row else None


async def get_row(facility_id: str, order_id: str) -> dict | None:
    """The raw orders row (UUID + status), SCOPED to the facility — for the
    action service which needs the DB id + current status. None if not ours."""
    return await database.fetchrow(
        "select o.* from orders o where o.facility_id = $1 and ("
        "  o.id::text = $2 "
        "  or upper(replace(o.order_id,' ','')) = upper(replace($2,' ','')))",
        facility_id, order_id,
    )


async def metrics(facility_id: str) -> dict:
    """Order counts per bucket for the facility (scoped)."""
    inc = _include_demo()
    row = await database.fetchrow(
        """
        select
          count(*) filter (where o.status = any($2::text[])) as in_count,
          count(*) filter (where o.status = any($3::text[])) as out_count,
          count(*) filter (where o.status = 'completed')     as completed_count,
          count(*) filter (
            where o.status <> all($4::text[])
              and o.pickup_date >= (now() at time zone 'Asia/Dubai')::date) as upcoming_count,
          count(*) filter (where o.status = any($5::text[])) as attention_status_count,
          count(*) as all_count
        from orders o
        where o.facility_id = $1 and (o.is_demo = false or $6)
        """,
        facility_id,
        list(BUCKET_STATUSES["in"]),
        list(BUCKET_STATUSES["out"]),
        list(_NON_TERMINAL_EXCLUDE),
        list(BUCKET_STATUSES["attention"]),
        inc,
    )
    issue_attention = await database.fetchval(
        "select count(distinct o.id) from orders o "
        "join facility_issues fi on fi.order_id = o.id "
        "where o.facility_id = $1 and fi.status not in ('resolved','closed') "
        "and o.status <> all($2::text[])",
        facility_id, list(BUCKET_STATUSES["attention"]),
    )
    return {
        "in": row["in_count"] if row else 0,
        "out": row["out_count"] if row else 0,
        "completed": row["completed_count"] if row else 0,
        "upcoming": row["upcoming_count"] if row else 0,
        "attention": (row["attention_status_count"] if row else 0) + (issue_attention or 0),
        "all": row["all_count"] if row else 0,
    }
