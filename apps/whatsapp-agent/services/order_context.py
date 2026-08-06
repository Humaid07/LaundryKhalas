"""Message → order context resolution + media→order linking (spec §15/§16/§17).

A customer may have several active/draft orders. This resolves which order a new
message belongs to (explicit id → active workflow → most-recent active → quoted /
payment / issue reference); when more than one active order could match and the
message is ambiguous, it returns ONE short clarification question rather than
guessing (guessing could change pricing/approval/payment). The pure resolver here
takes already-loaded candidates; the DB-backed link recorder is link_media_to_order.
"""
from __future__ import annotations

from db import database


def _match_ref(candidates: list[dict], ref: str | None) -> dict | None:
    if not ref:
        return None
    key = str(ref).strip().upper().replace(" ", "")
    for c in candidates:
        oref = str(c.get("order_ref") or "").upper().replace(" ", "")
        if oref and oref == key:
            return c
    return None


def resolve_order_context(
    *,
    candidates: list[dict],
    explicit_ref: str | None = None,
    quoted_ref: str | None = None,
    payment_ref: str | None = None,
    issue_ref: str | None = None,
) -> dict:
    """Return ``{order_id, order_ref, resolution, ambiguous, clarification_question?,
    candidates}``. ``candidates`` = active orders as ``{order_id, order_ref, status}``."""
    # 1. Explicit order reference in the message.
    for ref, label in ((explicit_ref, "explicit"), (quoted_ref, "quoted_ref"),
                       (payment_ref, "payment_ref"), (issue_ref, "issue_ref")):
        m = _match_ref(candidates, ref)
        if m:
            return {"order_id": m.get("order_id"), "order_ref": m.get("order_ref"),
                    "resolution": label, "ambiguous": False}

    active = [c for c in candidates if str(c.get("status", "")).lower() not in
              ("completed", "cancelled", "abandoned")]
    if len(active) == 1:
        c = active[0]
        return {"order_id": c.get("order_id"), "order_ref": c.get("order_ref"),
                "resolution": "single_active", "ambiguous": False}
    if len(active) == 0:
        return {"order_id": None, "order_ref": None, "resolution": "none", "ambiguous": False}

    # More than one active order + no explicit reference -> ask, never guess.
    refs = [c.get("order_ref") for c in active if c.get("order_ref")]
    question = None
    if len(refs) >= 2:
        question = f"Is this for order {refs[0]} or {refs[1]}?"
    return {"order_id": None, "order_ref": None, "resolution": "ambiguous",
            "ambiguous": True, "clarification_question": question,
            "candidates": [c.get("order_ref") for c in active]}


async def link_media_to_order(
    *, media_id: str | None, order_id: str, order_item_id: str | None = None,
    customer_id: str | None = None, conversation_id: str | None = None,
    provider_message_id: str | None = None, media_purpose: str | None = None,
    upload_source: str | None = None,
) -> dict | None:
    """Record a media→order/item link (media isolation). A photo is NEVER auto-reused
    across orders; reuse is an explicit, recorded event via this same path."""
    return await database.fetchrow(
        "insert into order_context_links (customer_id, conversation_id, order_id, order_item_id, "
        "provider_message_id, media_id, link_type, media_purpose, upload_source) "
        "values ($1,$2,$3,$4,$5,$6,'media',$7,$8) "
        "returning id, order_id, order_item_id, media_id, provider_message_id, link_type, created_at",
        customer_id, conversation_id, order_id, order_item_id, provider_message_id, media_id,
        media_purpose, upload_source)
