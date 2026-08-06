"""Facility revised-quote persistence (asyncpg / Supabase).

The state machine + customer-price computation live in the pure module
services/quote_revision.py; this repo only reads/writes rows. Facility-side reads
are scoped by facility_id; the internal (ops) inbox lists across all facilities.
The facility fee + margin are internal — ``customer_price`` is the only figure the
customer flow ever sees.
"""
from __future__ import annotations

from db import database

_COLS = (
    "id, order_id, order_item_id, facility_id, facility_issue_id, facility_fee, "
    "currency, reason, customer_price, status, created_by_user_id, created_by_label, "
    "reviewed_by, reviewed_at, customer_decided_at, created_at, updated_at"
)


def to_read(row: dict | None, *, include_fee: bool = True) -> dict | None:
    """Serialize a revision. ``include_fee=False`` strips the facility fee for any
    customer-facing path (defence-in-depth — the customer only sees customer_price)."""
    if not row:
        return None
    out = {
        "id": str(row["id"]),
        "order_id": str(row["order_id"]) if row.get("order_id") else None,
        "order_item_id": row.get("order_item_id"),
        "facility_id": str(row["facility_id"]) if row.get("facility_id") else None,
        "facility_issue_id": str(row["facility_issue_id"]) if row.get("facility_issue_id") else None,
        "currency": row.get("currency") or "AED",
        "reason": row.get("reason"),
        "customer_price": float(row["customer_price"]) if row.get("customer_price") is not None else None,
        "status": row.get("status"),
        "created_by_label": row.get("created_by_label"),
        "reviewed_by": row.get("reviewed_by"),
        "reviewed_at": row.get("reviewed_at"),
        "customer_decided_at": row.get("customer_decided_at"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }
    if include_fee:
        out["facility_fee"] = float(row["facility_fee"]) if row.get("facility_fee") is not None else None
    return out


async def create(
    *,
    order_uuid: str,
    facility_id: str,
    facility_fee,
    order_item_id: str | None = None,
    facility_issue_id: str | None = None,
    currency: str = "AED",
    reason: str | None = None,
    created_by_user_id: str | None = None,
    created_by_label: str | None = None,
) -> dict | None:
    row = await database.fetchrow(
        f"""
        insert into facility_quote_revisions
            (order_id, order_item_id, facility_id, facility_issue_id, facility_fee,
             currency, reason, status, created_by_user_id, created_by_label,
             is_test_data, is_demo, environment)
        values ($1, $2, $3, $4, $5, $6, $7, 'pending_ops_review', $8, $9,
                true, false, 'dev')
        returning {_COLS}
        """,
        order_uuid, order_item_id, facility_id, facility_issue_id, facility_fee,
        currency, reason, created_by_user_id, created_by_label,
    )
    return to_read(row)


async def get(revision_id: str, *, facility_id: str | None = None) -> dict | None:
    params: list = [revision_id]
    cond = "id = $1"
    if facility_id is not None:
        params.append(facility_id)
        cond += f" and facility_id = ${len(params)}"
    row = await database.fetchrow(f"select {_COLS} from facility_quote_revisions where {cond}", *params)
    return to_read(row)


async def list_for(facility_id: str | None = None, status: str | None = None) -> list[dict]:
    conds: list[str] = []
    params: list = []
    if facility_id is not None:
        params.append(facility_id)
        conds.append(f"facility_id = ${len(params)}")
    if status:
        params.append(status)
        conds.append(f"status = ${len(params)}")
    where = (" where " + " and ".join(conds)) if conds else ""
    rows = await database.fetch(
        f"select {_COLS} from facility_quote_revisions{where} order by created_at desc", *params)
    return [to_read(r) for r in rows]


async def set_review(
    revision_id: str, *, status: str, customer_price=None, reviewed_by: str | None = None
) -> dict | None:
    """Operations review outcome (ops_approved/customer_pending/ops_rejected) with
    the backend-computed customer price."""
    row = await database.fetchrow(
        f"""
        update facility_quote_revisions
           set status = $2,
               customer_price = coalesce($3, customer_price),
               reviewed_by = coalesce($4, reviewed_by),
               reviewed_at = now(),
               updated_at = now()
         where id = $1
        returning {_COLS}
        """,
        revision_id, status, customer_price, reviewed_by,
    )
    return to_read(row)


async def set_customer_decision(revision_id: str, *, status: str) -> dict | None:
    """Record the customer's decision (customer_approved / customer_rejected)."""
    row = await database.fetchrow(
        f"""
        update facility_quote_revisions
           set status = $2, customer_decided_at = now(), updated_at = now()
         where id = $1
        returning {_COLS}
        """,
        revision_id, status,
    )
    return to_read(row)


async def latest_pending_for_order(order_uuid: str) -> dict | None:
    """The most recent quote AWAITING a customer decision (status customer_pending)
    for the order, or None. Customer-safe (facility fee stripped) — this is what the
    agent relays. Never returns another order's quote (filtered by order_id)."""
    if not order_uuid:
        return None
    row = await database.fetchrow(
        f"select {_COLS} from facility_quote_revisions "
        "where order_id = $1::uuid and status = 'customer_pending' "
        "order by quote_version desc, created_at desc limit 1",
        order_uuid)
    return to_read(row)  # include_fee defaults False → customer-safe


async def status_for_order(order_uuid: str) -> str:
    """The revised-quote status for one order: pending | customer_pending |
    approved | none. Best-effort for the facility order view."""
    if not order_uuid:
        return "none"
    rows = await database.fetch(
        "select status from facility_quote_revisions where order_id = $1::uuid "
        "order by created_at desc", order_uuid)
    if not rows:
        return "none"
    latest = rows[0]["status"]
    return {
        "pending_ops_review": "pending",
        "ops_approved": "pending",
        "customer_pending": "customer_pending",
        "customer_approved": "approved",
    }.get(latest, "none")
