"""Structured order-notes persistence (asyncpg / Supabase).

The POLICY (validation, de-dup, correction, removal, snapshot) lives in the pure
module services/order_notes.py; this repo only reads/writes rows and writes audit
events. Every write is idempotent by the note dedupe_key + the partial-unique
index, so duplicate webhooks / repeated instructions never create duplicates.
"""

from __future__ import annotations

import json

from db import database
from services import order_notes as policy

_COLS = (
    "id, order_id, conversation_id, category, text, source, source_message_id, "
    "confidence, status, customer_confirmed, is_amendment, dedupe_key, superseded_by, "
    "created_at, updated_at"
)


def to_read(row: dict) -> dict:
    return {
        "note_id": str(row["id"]),
        "order_id": str(row["order_id"]) if row.get("order_id") else None,
        "category": row.get("category"),
        "text": row.get("text"),
        "source": row.get("source"),
        "source_message_id": row.get("source_message_id"),
        "confidence": float(row["confidence"]) if row.get("confidence") is not None else None,
        "status": row.get("status"),
        "customer_confirmed": bool(row.get("customer_confirmed")),
        "is_amendment": bool(row.get("is_amendment")),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


async def _audit(order_uuid: str, event_type: str, *, note_text: str | None = None, metadata: dict | None = None) -> None:
    try:
        await database.execute(
            "insert into order_events (order_id, event_type, actor_type, notes, metadata) "
            "values ($1, $2, 'customer', $3, $4::jsonb)",
            order_uuid, event_type, note_text, json.dumps(metadata or {}),
        )
    except Exception:  # audit must never break the write path
        pass


async def list_active(order_uuid: str) -> list[dict]:
    rows = await database.fetch(
        f"select {_COLS} from order_notes where order_id = $1 and status = 'ACTIVE' order by created_at asc",
        order_uuid,
    )
    return [dict(r) for r in rows]


async def list_all(order_uuid: str) -> list[dict]:
    rows = await database.fetch(
        f"select {_COLS} from order_notes where order_id = $1 order by created_at asc", order_uuid
    )
    return [dict(r) for r in rows]


async def _insert(order_uuid: str, plan: policy.MergePlan, *, conversation_id, source, source_message_id, confidence, is_amendment) -> dict | None:
    row = await database.fetchrow(
        "insert into order_notes (order_id, conversation_id, category, text, source, "
        "source_message_id, confidence, is_amendment, dedupe_key, is_test_data) "
        "values ($1,$2,$3,$4,$5,$6,$7,$8,$9,false) "
        "on conflict (order_id, dedupe_key) where status = 'ACTIVE' do nothing "
        f"returning {_COLS}",
        order_uuid, conversation_id, plan.category, plan.text, source,
        source_message_id, confidence, is_amendment, plan.dedupe,
    )
    return dict(row) if row else None


async def apply_candidate(
    order_uuid: str,
    *,
    category: str,
    text: str,
    source: str = "CUSTOMER_MESSAGE",
    source_message_id: str | None = None,
    confidence: float | None = None,
    conversation_id: str | None = None,
    is_amendment: bool = False,
) -> dict:
    """Validate + de-dup + (maybe) supersede + insert one candidate note.

    Returns ``{"action": ..., "note": {...}|None, "reason": ...}``.
    """
    existing = await list_active(order_uuid)
    plan = policy.plan_note_merge(order_uuid, existing, category, text)

    if plan.action is policy.MergeAction.REJECTED:
        return {"action": "rejected", "note": None, "reason": plan.reason}
    if plan.action is policy.MergeAction.DUPLICATE:
        await _audit(order_uuid, "duplicate_voice_message_ignored" if False else "order_note_detected",
                     note_text=plan.text, metadata={"result": "duplicate", "category": plan.category})
        return {"action": "duplicate", "note": None, "reason": "duplicate"}

    if plan.action is policy.MergeAction.SUPERSEDE and plan.supersedes_id:
        await database.execute(
            "update order_notes set status='SUPERSEDED', updated_at=now() where id = $1", plan.supersedes_id
        )

    row = await _insert(
        order_uuid, plan, conversation_id=conversation_id, source=source,
        source_message_id=source_message_id, confidence=confidence, is_amendment=is_amendment,
    )
    if not row:  # lost a concurrent race on the unique index → treat as duplicate
        return {"action": "duplicate", "note": None, "reason": "conflict"}

    if plan.supersedes_id:
        await database.execute("update order_notes set superseded_by=$1 where id=$2", row["id"], plan.supersedes_id)
        await _audit(order_uuid, "order_note_updated", note_text=plan.text,
                     metadata={"category": plan.category, "superseded": str(plan.supersedes_id)})
        action = "updated"
    else:
        await _audit(order_uuid, "order_note_added", note_text=plan.text,
                     metadata={"category": plan.category, "source": source, "is_amendment": is_amendment})
        action = "added"
    return {"action": action, "note": to_read(row), "reason": plan.reason}


async def remove(order_uuid: str, *, target_text: str | None = None, category: str | None = None) -> list[str]:
    existing = await list_active(order_uuid)
    ids = policy.find_notes_to_remove(existing, target_text=target_text, category=category)
    for nid in ids:
        await database.execute(
            "update order_notes set status='REMOVED', updated_at=now() where id=$1 and status='ACTIVE'", nid
        )
    if ids:
        await _audit(order_uuid, "order_note_removed", note_text=target_text,
                     metadata={"removed_ids": ids, "category": category})
    return ids


async def confirm_active(order_uuid: str) -> list[dict]:
    """Mark all ACTIVE notes customer-confirmed and return the immutable snapshot."""
    existing = await list_active(order_uuid)
    await database.execute(
        "update order_notes set customer_confirmed=true, updated_at=now() "
        "where order_id=$1 and status='ACTIVE'",
        order_uuid,
    )
    snapshot = policy.build_confirmed_snapshot(existing)
    await _audit(order_uuid, "order_notes_confirmed", metadata={"count": len(snapshot)})
    return snapshot


async def grouped_active(order_uuid: str) -> dict[str, list[str]]:
    return policy.group_active_by_category(await list_active(order_uuid))
