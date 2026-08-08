"""Durable follow-up queue (Supabase dev/test schema) — spec §§14, 24, 25.

Thin CRUD over ``scheduled_followups`` (migration 000042). It stores and loads rows;
the scheduling POLICY (timing, cutoff, suppression, arbitration) is pure and lives in
``services/followups`` + ``services/followup_scheduler``. ``schedule`` is idempotent via
the unique ``dedupe_key`` (ON CONFLICT DO NOTHING) so re-running the same event never
duplicates a follow-up. ``cancel_for_conversation`` is the fast path for "customer
replied / opted out" — it drops every still-pending follow-up for that conversation.
"""
from __future__ import annotations

import datetime as _dt
import json as _json

from db import database

_COLS = (
    "id, conversation_id, order_id, customer_phone, followup_type, status, template_id, "
    "dedupe_key, due_at, anchor_at, market, persona, payload, suppressed_reason, "
    "created_at, updated_at, sent_at, cancelled_at"
)


def _serialize(row: dict | None) -> dict | None:
    if not row:
        return None
    d = dict(row)
    for k in ("id", "conversation_id"):
        if d.get(k) is not None:
            d[k] = str(d[k])
    return d


async def schedule(rows: list[dict]) -> int:
    """Insert new follow-up rows, skipping any whose ``dedupe_key`` already exists
    (idempotent). Returns the number actually inserted."""
    inserted = 0
    for r in rows:
        row = await database.fetchrow(
            """
            insert into scheduled_followups
                (conversation_id, order_id, customer_phone, followup_type, status,
                 template_id, dedupe_key, due_at, anchor_at, market, persona, payload)
            values ($1::uuid, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12::jsonb)
            on conflict (dedupe_key) do nothing
            returning id
            """,
            r.get("conversation_id"), r.get("order_id"), r.get("customer_phone"),
            r["followup_type"], r.get("status", "PENDING"), r.get("template_id"),
            r["dedupe_key"], r["due_at"], r.get("anchor_at"), r.get("market", "AE"),
            r.get("persona"), _json.dumps(r["payload"]) if r.get("payload") is not None else None,
        )
        if row is not None:
            inserted += 1
    return inserted


async def web_abandonment_status(number: str) -> str | None:
    """The §24/§29 website-abandonment status for a number: sent | scheduled | cancelled,
    or None when nothing was ever scheduled. Best-effort read."""
    if not number:
        return None
    rows = await database.fetch(
        "select status from scheduled_followups "
        "where customer_phone = $1 and followup_type like 'WEB_ABANDONMENT%'",
        number)
    if not rows:
        return None
    statuses = {r["status"] for r in rows}
    if "SENT" in statuses:
        return "sent"
    if "PENDING" in statuses:
        return "scheduled"
    if "CANCELLED" in statuses:
        return "cancelled"
    return "suppressed"


async def load_due(now: _dt.datetime, *, limit: int = 200) -> list[dict]:
    """PENDING follow-ups whose due time has passed, oldest first. The caller applies
    the policy (window + suppression + arbitration) before sending."""
    rows = await database.fetch(
        f"""
        select {_COLS} from scheduled_followups
         where status = 'PENDING' and due_at <= $1
         order by due_at asc
         limit $2
        """,
        now, int(limit),
    )
    return [_serialize(r) for r in rows]


async def mark_sent(followup_id: str) -> None:
    await database.execute(
        "update scheduled_followups set status = 'SENT', sent_at = now(), updated_at = now() "
        "where id = $1::uuid",
        followup_id,
    )


async def mark_suppressed(followup_id: str, reason: str) -> None:
    await database.execute(
        "update scheduled_followups set status = 'SUPPRESSED', suppressed_reason = $2, "
        "updated_at = now() where id = $1::uuid",
        followup_id, reason,
    )


async def cancel_for_conversation(conversation_id: str, reason: str = "customer_replied") -> int:
    """Cancel every still-PENDING follow-up for a conversation (customer replied /
    opted out / order settled). Returns the number cancelled."""
    rows = await database.fetch(
        "update scheduled_followups set status = 'CANCELLED', suppressed_reason = $2, "
        "cancelled_at = now(), updated_at = now() "
        "where conversation_id = $1::uuid and status = 'PENDING' returning id",
        conversation_id, reason,
    )
    return len(rows)
