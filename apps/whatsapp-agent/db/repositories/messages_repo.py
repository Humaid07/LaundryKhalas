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
) -> dict | None:
    row = await database.fetchrow(
        """
        insert into messages
            (conversation_id, sender_type, message_text, is_internal, status,
             is_test_data, is_demo, environment, created_by_seed)
        values ($1, $2, $3, $4, $5, false, false, 'dev', false)
        returning id, conversation_id, sender_type, message_text, is_internal, status,
                  metadata, is_test_data, is_demo, environment, test_scenario_id, created_at
        """,
        conversation_id,
        sender_type,
        message_text,
        is_internal,
        status,
    )
    # Keep the conversation preview in sync for non-internal messages.
    if not is_internal:
        await conversations_repo.touch_last_message(conversation_id, message_text)
    return row
