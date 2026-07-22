"""Support-ticket writes against the dev/test Supabase schema.

Raised alongside an agent_flag when a conversation needs human handling
(refund / complaint / damaged / missing item / payment issue / …). A ticket is
the durable work item the ops team resolves; the flag is the inbox signal.

``create_or_update`` is idempotent per (conversation, ticket_type): a repeat of
the same concern on the same conversation updates the open ticket instead of
piling up duplicates.
"""
from __future__ import annotations

from db import database

_SELECT = """
  select id, conversation_id, order_id, ticket_type, priority, assigned_team,
         status, title, description, is_test_data, is_demo, environment,
         test_scenario_id, created_at, updated_at, resolved_at
    from tickets
"""


async def create_or_update(
    *,
    conversation_id: str,
    ticket_type: str,
    priority: str,
    assigned_team: str,
    title: str | None = None,
    description: str | None = None,
    order_uuid: str | None = None,
) -> dict | None:
    existing = await database.fetchrow(
        "select id from tickets where conversation_id = $1 and ticket_type = $2 "
        "and status = 'open' order by created_at desc limit 1",
        conversation_id,
        ticket_type,
    )
    if existing:
        return await database.fetchrow(
            """
            update tickets
               set priority = $2, assigned_team = $3, title = coalesce($4, title),
                   description = coalesce($5, description),
                   order_id = coalesce($6, order_id)
             where id = $1
            returning id, conversation_id, order_id, ticket_type, priority,
                      assigned_team, status, title, description, created_at,
                      updated_at, resolved_at
            """,
            existing["id"],
            priority,
            assigned_team,
            title,
            description,
            order_uuid,
        )
    return await database.fetchrow(
        """
        insert into tickets
            (conversation_id, order_id, ticket_type, priority, assigned_team,
             status, title, description, is_test_data, is_demo, environment,
             test_scenario_id, created_by_seed)
        values ($1, $2, $3, $4, $5, 'open', $6, $7, true, false, 'dev',
                'whatsapp_live_capture', false)
        returning id, conversation_id, order_id, ticket_type, priority,
                  assigned_team, status, title, description, created_at,
                  updated_at, resolved_at
        """,
        conversation_id,
        order_uuid,
        ticket_type,
        priority,
        assigned_team,
        title,
        description,
    )


async def list_tickets(status: str | None = None) -> list[dict]:
    if status:
        return await database.fetch(
            _SELECT + " where status = $1 order by created_at desc", status
        )
    return await database.fetch(_SELECT + " order by created_at desc")
