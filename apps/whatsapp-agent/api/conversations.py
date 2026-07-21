"""WhatsApp inbox conversation API.

Backed by the dev/test Supabase schema when DATABASE_MODE=supabase. In local
SQLite mode these inbox endpoints degrade gracefully (empty list / 503) — the
rich conversation/flag model lives in the Supabase schema, while the existing
SQLite chat + order flow keeps working unchanged.

Dashboard → FastAPI → Supabase. Customer messages are NOT authored here; only
human-operator replies during a takeover.
"""
from fastapi import APIRouter, HTTPException

from db import database
from db.repositories import conversations_repo, messages_repo
from schemas import HumanMessageRequest, HumanTakeoverRequest

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


def _require_supabase():
    if not database.is_supabase_mode():
        raise HTTPException(
            status_code=503,
            detail="Conversation inbox requires DATABASE_MODE=supabase (dev/test Supabase project).",
        )


@router.get("")
async def list_conversations(status: str | None = None):
    # Empty (not an error) in local mode so the dashboard renders cleanly.
    if not database.is_supabase_mode():
        return []
    return await conversations_repo.list_conversations(status=status)


@router.get("/{conversation_id}")
async def get_conversation(conversation_id: str):
    _require_supabase()
    convo = await conversations_repo.get_conversation(conversation_id)
    if convo is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return convo


@router.get("/{conversation_id}/messages")
async def get_messages(conversation_id: str):
    if not database.is_supabase_mode():
        return []
    return await messages_repo.list_messages(conversation_id)


@router.post("/{conversation_id}/human-takeover")
async def human_takeover(conversation_id: str, payload: HumanTakeoverRequest | None = None):
    _require_supabase()
    operator = payload.operator_name if payload else None
    convo = await conversations_repo.start_human_takeover(conversation_id, operator)
    if convo is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return convo


@router.post("/{conversation_id}/return-to-bot")
async def return_to_bot(conversation_id: str):
    _require_supabase()
    convo = await conversations_repo.return_to_bot(conversation_id)
    if convo is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return convo


@router.post("/{conversation_id}/human-message")
async def human_message(conversation_id: str, payload: HumanMessageRequest):
    _require_supabase()
    text = (payload.text or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="Message text is required.")
    # Ensure a takeover is active, then store the operator's reply.
    await conversations_repo.start_human_takeover(conversation_id, payload.operator_name)
    message = await messages_repo.add_message(conversation_id, "human", text)
    if message is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return message


@router.post("/{conversation_id}/resolve")
async def resolve_conversation(conversation_id: str):
    _require_supabase()
    convo = await conversations_repo.resolve(conversation_id)
    if convo is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return convo
