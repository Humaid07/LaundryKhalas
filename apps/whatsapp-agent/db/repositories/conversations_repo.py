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


# --------------------------------------------------------------------------
# Inbound (Evolution / real WhatsApp) helpers
# --------------------------------------------------------------------------
async def get_or_create_for_customer(
    customer_id: str, channel: str = "whatsapp", external_id: str | None = None
) -> dict:
    """Latest non-resolved conversation for the customer, or a new bot-handled one."""
    existing = await database.fetchrow(
        "select * from conversations where customer_id = $1 and status <> 'resolved' "
        "order by last_message_at desc nulls last limit 1",
        customer_id,
    )
    if existing:
        return existing
    return await database.fetchrow(
        """
        insert into conversations
            (customer_id, external_conversation_id, channel, status, unread_count,
             is_test_data, is_demo, environment, created_by_seed)
        values ($1, $2, $3, 'bot', 0, false, false, 'dev', false)
        returning *
        """,
        customer_id,
        external_id,
        channel,
    )


async def register_inbound(conversation_id: str, text: str) -> None:
    """Bump the preview + unread counter for a newly-received customer message."""
    await database.execute(
        "update conversations set last_message = $2, last_message_at = now(), "
        "unread_count = unread_count + 1 where id = $1",
        conversation_id,
        text,
    )


async def set_flagged(conversation_id: str, *, reason: str, priority: str, team: str) -> None:
    await database.execute(
        """
        update conversations
           set status = 'human_needed',
               priority = $2,
               human_intervention_required = true,
               handoff_reason = $3,
               assigned_team = $4
         where id = $1 and status <> 'human_takeover'
        """,
        conversation_id,
        priority,
        reason,
        team,
    )


async def get_customer_phone(conversation_id: str) -> str | None:
    """Backend-only: the real phone (phone_e164) needed to send an outbound
    reply. Never returned by the read APIs (those expose masked_phone only)."""
    return await database.fetchval(
        "select cust.phone_e164 from conversations c "
        "join customers cust on cust.id = c.customer_id where c.id = $1",
        conversation_id,
    )
