"""Order reads/writes against the dev/test Supabase schema.

Rows are mapped to the existing ``OrderRead`` shape so the same FastAPI order
endpoints serve either SQLite (local) or Supabase (dev/test) data unchanged.
"""
from __future__ import annotations

from db import database
from services import order_store  # reuse status_label + active-status logic

_TERMINAL = {order_store.COMPLETED, order_store.CANCELLED}
_HIDDEN_FROM_ACTIVE = _TERMINAL | {order_store.DRAFT}

_SELECT = "select * from orders"


def to_read(row: dict) -> dict:
    """Map a Supabase orders row to the OrderRead schema shape."""
    status = row.get("status") or "active"
    items = row.get("items") or []
    if isinstance(items, str):
        items = [items]
    return {
        "id": str(row["id"]),
        "order_id": row["order_id"],
        "conversation_id": str(row["conversation_id"]) if row.get("conversation_id") else None,
        "customer_name": row.get("customer_name"),
        "service_type": row.get("service"),
        "items": [str(i) for i in items],
        "pickup_area": row.get("area"),
        "pickup_address": None,
        "pickup_date": row.get("pickup_slot"),
        "pickup_time": None,
        "city": row.get("city"),
        "delivery_preference": row.get("delivery_slot"),
        "status": status,
        "status_label": order_store.status_label(status),
        "notes": row.get("notes"),
        "change_request": row.get("change_request"),
        "amount": float(row["amount"]) if row.get("amount") is not None else None,
        "currency": "AED",
        "facility": row.get("facility"),
        "driver": row.get("driver"),
        "payment": row.get("payment_status"),
        "source_channel": row.get("source_channel") or "whatsapp",
        "is_demo": bool(row.get("is_demo")),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "completed_at": row.get("completed_at"),
    }


async def list_active_read() -> list[dict]:
    rows = await database.fetch(
        _SELECT + " where status <> all($1::text[]) order by updated_at desc",
        list(_HIDDEN_FROM_ACTIVE),
    )
    return [to_read(r) for r in rows]


async def list_completed_read() -> list[dict]:
    rows = await database.fetch(
        _SELECT + " where status = $1 order by completed_at desc nulls last",
        order_store.COMPLETED,
    )
    return [to_read(r) for r in rows]


async def list_read(status: str | None = None) -> list[dict]:
    if status:
        rows = await database.fetch(_SELECT + " where status = $1 order by updated_at desc", status)
    else:
        rows = await database.fetch(_SELECT + " order by updated_at desc")
    return [to_read(r) for r in rows]


async def get_read(order_id: str) -> dict | None:
    row = await database.fetchrow(
        _SELECT + " where upper(replace(order_id,' ','')) = upper(replace($1,' ','')) ",
        order_id,
    )
    return to_read(row) if row else None


async def complete(order_id: str) -> dict | None:
    row = await database.fetchrow(
        "update orders set status = 'completed', completed_at = now() "
        "where upper(replace(order_id,' ','')) = upper(replace($1,' ','')) returning *",
        order_id,
    )
    return to_read(row) if row else None


async def set_status(order_id: str, status: str) -> dict | None:
    if status not in order_store.ORDER_STATUSES:
        raise ValueError(f"Unknown status: {status}")
    completed_at = ", completed_at = now()" if status == order_store.COMPLETED else ""
    row = await database.fetchrow(
        f"update orders set status = $2{completed_at} "
        "where upper(replace(order_id,' ','')) = upper(replace($1,' ','')) returning *",
        order_id,
        status,
    )
    return to_read(row) if row else None


async def metrics() -> dict:
    rows = await database.fetch("select status from orders")
    by_status: dict[str, int] = {}
    for r in rows:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
    return {
        "active_orders": sum(v for k, v in by_status.items() if k not in _HIDDEN_FROM_ACTIVE),
        "completed_orders": by_status.get(order_store.COMPLETED, 0),
        "cancellation_requests": by_status.get(order_store.CANCELLATION_REQUESTED, 0),
        "pickup_change_requests": by_status.get(order_store.PICKUP_CHANGE_REQUESTED, 0),
        "support_required": by_status.get(order_store.SUPPORT_REQUIRED, 0),
        "total_orders": len(rows),
        "orders_by_status": by_status,
    }
