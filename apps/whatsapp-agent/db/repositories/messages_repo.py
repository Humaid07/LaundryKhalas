"""Message reads/writes against the dev/test Supabase schema."""
from __future__ import annotations

from db import database
from db.repositories import conversations_repo

_SELECT = """
  select id, conversation_id, sender_type, message_text, is_internal, status,
         metadata, is_test_data, is_demo, environment, test_scenario_id, created_at
    from messages
"""


async def list_messages(conversation_id: str) -> list[dict]:
    return await database.fetch(
        _SELECT + " where conversation_id = $1 order by created_at asc", conversation_id
    )


async def add_message(
    conversation_id: str,
    sender_type: str,
    message_text: str,
    *,
    is_internal: bool = False,
    status: str = "sent",
    metadata: dict | None = None,
) -> dict | None:
    """Store a message. ``metadata`` (jsonb) carries derived signals like intent /
    domain / auto_reply_decision on inbound + agent rows (never raw PII)."""
    row = await database.fetchrow(
        """
        insert into messages
            (conversation_id, sender_type, message_text, is_internal, status,
             metadata, is_test_data, is_demo, environment, created_by_seed)
        values ($1, $2, $3, $4, $5, $6::jsonb, false, false, 'dev', false)
        returning id, conversation_id, sender_type, message_text, is_internal, status,
                  metadata, is_test_data, is_demo, environment, test_scenario_id, created_at
        """,
        conversation_id,
        sender_type,
        message_text,
        is_internal,
        status,
        metadata or {},
    )
    # Keep the conversation preview in sync for non-internal messages.
    if not is_internal:
        await conversations_repo.touch_last_message(conversation_id, message_text)
    return row


async def has_agent_reply(conversation_id: str) -> bool:
    """True if the agent has already sent at least one message in this
    conversation — used to enforce 'welcome only once' so the auto-reply never
    re-greets an ongoing chat."""
    val = await database.fetchval(
        "select 1 from messages where conversation_id = $1 and sender_type = 'agent' limit 1",
        conversation_id,
    )
    return bool(val)


async def set_status(message_id: str, status: str) -> None:
    """Update a stored message's status (e.g. mark an inbound 'no_auto_reply'
    when the auto-reply decision layer chose not to respond)."""
    await database.execute(
        "update messages set status = $2 where id = $1", message_id, status
    )
