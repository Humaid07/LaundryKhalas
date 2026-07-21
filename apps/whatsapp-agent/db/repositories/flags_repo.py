"""Agent-flag (handoff/escalation) reads/writes against the dev/test Supabase schema."""
from __future__ import annotations

from db import database

_SELECT = """
  select f.id, f.conversation_id, f.order_id, f.flag_type, f.priority,
         f.assigned_team, f.human_intervention_required, f.reason,
         f.suggested_reply, f.suggested_action, f.status, f.metadata,
         f.is_test_data, f.is_demo, f.environment, f.test_scenario_id,
         f.created_at, f.resolved_at
    from agent_flags f
"""


async def create(
    *,
    conversation_id: str,
    flag_type: str,
    priority: str,
    assigned_team: str,
    reason: str | None = None,
    suggested_reply: str | None = None,
    suggested_action: str | None = None,
    order_id: str | None = None,
) -> dict | None:
    return await database.fetchrow(
        """
        insert into agent_flags
            (conversation_id, order_id, flag_type, priority, assigned_team,
             human_intervention_required, reason, suggested_reply, suggested_action,
             status, is_test_data, is_demo, environment, created_by_seed)
        values ($1, $2, $3, $4, $5, true, $6, $7, $8, 'open', false, false, 'dev', false)
        returning id, conversation_id, order_id, flag_type, priority, assigned_team,
                  human_intervention_required, reason, suggested_reply, suggested_action,
                  status, metadata, is_test_data, is_demo, environment, test_scenario_id,
                  created_at, resolved_at
        """,
        conversation_id,
        order_id,
        flag_type,
        priority,
        assigned_team,
        reason,
        suggested_reply,
        suggested_action,
    )


async def list_flags(status: str | None = None) -> list[dict]:
    if status:
        return await database.fetch(_SELECT + " where f.status = $1 order by f.created_at desc", status)
    return await database.fetch(_SELECT + " order by f.created_at desc")


async def resolve(flag_id: str) -> dict | None:
    return await database.fetchrow(
        "update agent_flags set status = 'resolved', resolved_at = now() where id = $1 "
        "returning id, conversation_id, order_id, flag_type, priority, assigned_team, "
        "human_intervention_required, reason, suggested_reply, suggested_action, status, "
        "metadata, is_test_data, is_demo, environment, test_scenario_id, created_at, resolved_at",
        flag_id,
    )
