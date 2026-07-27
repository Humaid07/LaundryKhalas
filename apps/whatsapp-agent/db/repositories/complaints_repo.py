"""Structured complaint records (Supabase dev/test schema).

A complaint is raised for Operations to resolve — the agent never promises a
refund/compensation (CLAUDE.md §6). ``create`` inserts one row with a generated
``complaint_ref`` (CMP-XXXXXXXX). Reads are for the ops dashboard/metrics.
"""
from __future__ import annotations

from db import database
from services import complaints as complaints_svc

_COLS = (
    "id, complaint_ref, customer_id, conversation_id, order_id, order_ref, "
    "category, affected_item, description, photo_ref, requested_resolution, "
    "needs_recollection, urgency, status, source, resolution_notes, "
    "created_at, updated_at, resolved_at"
)


def _serialize(row: dict | None) -> dict | None:
    if not row:
        return None
    d = dict(row)
    for k in ("id", "customer_id", "conversation_id", "order_id"):
        if d.get(k) is not None:
            d[k] = str(d[k])
    return d


async def create(
    *,
    customer_id: str | None,
    conversation_id: str | None,
    category: str,
    order_id: str | None = None,
    order_ref: str | None = None,
    affected_item: str | None = None,
    description: str | None = None,
    photo_ref: str | None = None,
    requested_resolution: str | None = None,
    needs_recollection: bool = False,
    urgency: str = "medium",
    source: str = "whatsapp",
) -> dict | None:
    """Insert a complaint. Category is validated against the known taxonomy
    (unknown → 'other') so a bad value never lands in the DB."""
    if category not in complaints_svc.CATEGORIES:
        category = "other"
    row = await database.fetchrow(
        f"""
        insert into complaints
            (complaint_ref, customer_id, conversation_id, order_id, order_ref,
             category, affected_item, description, photo_ref, requested_resolution,
             needs_recollection, urgency, status, source)
        values (
            'CMP-' || upper(substr(replace(gen_random_uuid()::text, '-', ''), 1, 8)),
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, 'open', $12
        )
        returning {_COLS}
        """,
        customer_id, conversation_id, order_id, order_ref, category,
        affected_item, description, photo_ref, requested_resolution,
        needs_recollection, urgency, source,
    )
    return _serialize(row)


async def get(complaint_id: str) -> dict | None:
    row = await database.fetchrow(
        f"select {_COLS} from complaints where id = $1", complaint_id
    )
    return _serialize(row)


async def list_open(limit: int = 100) -> list[dict]:
    rows = await database.fetch(
        f"select {_COLS} from complaints where status in ('open','in_review') "
        f"order by created_at desc limit {max(1, min(int(limit), 200))}"
    )
    return [_serialize(r) for r in rows]


async def set_status(complaint_id: str, status: str, *, resolution_notes: str | None = None) -> dict | None:
    resolved = ", resolved_at = now()" if status in ("resolved", "closed") else ""
    row = await database.fetchrow(
        f"""
        update complaints set status = $2, resolution_notes = coalesce($3, resolution_notes){resolved}
         where id = $1 returning {_COLS}
        """,
        complaint_id, status, resolution_notes,
    )
    return _serialize(row)
