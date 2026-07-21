"""Conversation reads/writes against the dev/test Supabase schema."""
from __future__ import annotations

from db import database

# Columns returned to the API / dashboard. Customer name + masked phone are
# joined from customers; the full phone is never selected here.
_SELECT = """
  select c.id,
         c.customer_id,
         cust.display_name        as customer_name,
         cust.masked_phone        as masked_phone,
         c.channel,
         c.status,
         c.priority,
         c.human_intervention_required,
         c.handoff_reason,
         c.assigned_team,
         c.linked_order_id,
         cust.city                as city,
         cust.area                as area,
         c.last_message,
         c.last_message_at,
         c.unread_count,
         c.is_test_data,
         c.is_demo,
         c.environment,
         c.test_scenario_id,
         c.created_at,
         c.updated_at
    from conversations c
    left join customers cust on cust.id = c.customer_id
"""


async def list_conversations(status: str | None = None) -> list[dict]:
    if status:
        return await database.fetch(
            _SELECT + " where c.status = $1 order by c.last_message_at desc nulls last", status
        )
    return await database.fetch(_SELECT + " order by c.last_message_at desc nulls last")


async def get_conversation(conversation_id: str) -> dict | None:
    return await database.fetchrow(_SELECT + " where c.id = $1", conversation_id)


async def start_human_takeover(conversation_id: str, operator_name: str | None) -> dict | None:
    await database.execute(
        """
        update conversations
           set status = 'human_takeover',
               human_intervention_required = true
         where id = $1
        """,
        conversation_id,
    )
    await database.execute(
        """
        insert into human_takeovers
            (conversation_id, operator_name, status, is_test_data, is_demo, environment, created_by_seed)
        values ($1, $2, 'active', false, false, 'dev', false)
        """,
        conversation_id,
        operator_name or "Operator",
    )
    return await get_conversation(conversation_id)


async def return_to_bot(conversation_id: str) -> dict | None:
    await database.execute(
        """
        update conversations
           set status = 'bot',
               priority = null,
               human_intervention_required = false,
               handoff_reason = null
         where id = $1
        """,
        conversation_id,
    )
    await database.execute(
        "update human_takeovers set status = 'ended', ended_at = now() "
        "where conversation_id = $1 and status = 'active'",
        conversation_id,
    )
    return await get_conversation(conversation_id)


async def resolve(conversation_id: str) -> dict | None:
    await database.execute(
        "update conversations set status = 'resolved', unread_count = 0 where id = $1",
        conversation_id,
    )
    await database.execute(
        "update human_takeovers set status = 'ended', ended_at = now() "
        "where conversation_id = $1 and status = 'active'",
        conversation_id,
    )
    return await get_conversation(conversation_id)


async def touch_last_message(conversation_id: str, text: str) -> None:
    await database.execute(
        "update conversations set last_message = $2, last_message_at = now() where id = $1",
        conversation_id,
        text,
    )
