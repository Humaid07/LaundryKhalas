"""Website Order-Now intent queries (Supabase) — spec §24.

Records are written by the /api/web/order-intent endpoint (via the ORM). This repo is the
raw-asyncpg read/update path used by the live webhook + follow-up sweeper: when the visitor
finally messages on WhatsApp we mark their intent converted, which suppresses the pending
abandonment follow-ups (they became a real conversation, so no nudge is needed).
"""
from __future__ import annotations

from db import database


async def mark_converted_by_number(number: str) -> int:
    """Mark every still-open intent for this WhatsApp number as converted (the visitor
    messaged us). Returns how many were flipped."""
    if not number:
        return 0
    rows = await database.fetch(
        "update web_order_intents set converted = true, updated_at = now() "
        "where whatsapp_number = $1 and converted = false returning id",
        number)
    return len(rows)


async def status_for_number(number: str) -> str | None:
    """Latest intent status for a number (spec §29 dashboard): converted | consented |
    captured, or None when there's no intent. Best-effort read."""
    if not number:
        return None
    r = await database.fetchrow(
        "select converted, consent from web_order_intents "
        "where whatsapp_number = $1 order by created_at desc limit 1",
        number)
    if r is None:
        return None
    if r.get("converted"):
        return "converted"
    return "consented" if r.get("consent") else "captured"


async def is_converted_number(number: str) -> bool:
    """True when this number already converted (used to suppress abandonment follow-ups)."""
    if not number:
        return False
    r = await database.fetchrow(
        "select 1 from web_order_intents where whatsapp_number = $1 and converted = true limit 1",
        number)
    return r is not None
