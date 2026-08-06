"""Durable customer-memory persistence (asyncpg / Supabase).

Thin row I/O; the PATCH/scope POLICY lives in the pure services/customer_memory_store.py
and the orchestration in services/customer_memory_service.py. One ACTIVE value per
(customer, memory_key, scope) is guaranteed by a partial-unique index; corrections
supersede the old row and write a history entry (never a silent delete).
"""
from __future__ import annotations

from db import database

_COLS = (
    "id, customer_id, memory_type, memory_key, memory_value, source_message_id, "
    "source_order_id, scope, confidence, customer_confirmed, status, valid_from, "
    "invalidated_at, created_at, updated_at"
)


def to_read(row: dict) -> dict:
    return {
        "id": str(row["id"]),
        "customer_id": str(row["customer_id"]) if row.get("customer_id") else None,
        "memory_type": row.get("memory_type"),
        "memory_key": row.get("memory_key"),
        "memory_value": row.get("memory_value"),
        "scope": row.get("scope"),
        "confidence": float(row["confidence"]) if row.get("confidence") is not None else None,
        "customer_confirmed": bool(row.get("customer_confirmed")),
        "status": row.get("status"),
        "source_message_id": row.get("source_message_id"),
        "source_order_id": str(row["source_order_id"]) if row.get("source_order_id") else None,
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


async def list_active(customer_id: str) -> list[dict]:
    rows = await database.fetch(
        f"select {_COLS} from customer_memory where customer_id = $1 and status = 'active' "
        "order by memory_key, scope", customer_id)
    return [dict(r) for r in rows]


async def insert(
    *, customer_id: str, memory_type: str, memory_key: str, memory_value: str,
    scope: str, confidence=None, customer_confirmed: bool = True,
    source_message_id: str | None = None, source_order_id: str | None = None,
) -> dict | None:
    row = await database.fetchrow(
        f"""
        insert into customer_memory
            (customer_id, memory_type, memory_key, memory_value, source_message_id,
             source_order_id, scope, confidence, customer_confirmed, status, is_test_data)
        values ($1,$2,$3,$4,$5,$6,$7,$8,$9,'active',false)
        on conflict (customer_id, memory_key, scope) where status = 'active' do nothing
        returning {_COLS}
        """,
        customer_id, memory_type, memory_key, memory_value, source_message_id,
        source_order_id, scope, confidence, customer_confirmed,
    )
    return to_read(row) if row else None


async def mark_superseded(memory_id: str) -> None:
    await database.execute(
        "update customer_memory set status = 'superseded', invalidated_at = now(), "
        "updated_at = now() where id = $1 and status = 'active'", memory_id)


async def invalidate(customer_id: str, memory_key: str, scope: str) -> None:
    await database.execute(
        "update customer_memory set status = 'invalidated', invalidated_at = now(), "
        "updated_at = now() where customer_id = $1 and memory_key = $2 and scope = $3 "
        "and status = 'active'", customer_id, memory_key, scope)


async def add_history(
    *, customer_id: str, memory_id: str | None, memory_key: str,
    old_value: str | None, new_value: str | None, reason: str,
) -> None:
    await database.execute(
        "insert into customer_memory_history (customer_id, memory_id, memory_key, "
        "old_value, new_value, reason) values ($1,$2,$3,$4,$5,$6)",
        customer_id, memory_id, memory_key, old_value, new_value, reason)
