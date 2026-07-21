"""Human-takeover reads/writes against the dev/test Supabase schema.

Note: starting/ending a takeover also flips the parent conversation status —
that combined behaviour lives in ``conversations_repo`` (start_human_takeover /
return_to_bot / resolve). These helpers are the direct table accessors.
"""
from __future__ import annotations

from db import database

_SELECT = """
  select id, conversation_id, operator_name, status, started_at, ended_at, notes,
         is_test_data, is_demo, environment, test_scenario_id
    from human_takeovers
"""


async def list_takeovers(conversation_id: str | None = None, status: str | None = None) -> list[dict]:
    clauses, args = [], []
    if conversation_id:
        args.append(conversation_id)
        clauses.append(f"conversation_id = ${len(args)}")
    if status:
        args.append(status)
        clauses.append(f"status = ${len(args)}")
    where = (" where " + " and ".join(clauses)) if clauses else ""
    return await database.fetch(_SELECT + where + " order by started_at desc", *args)


async def active_for_conversation(conversation_id: str) -> dict | None:
    return await database.fetchrow(
        _SELECT + " where conversation_id = $1 and status = 'active' order by started_at desc limit 1",
        conversation_id,
    )


async def start(conversation_id: str, operator_name: str | None) -> dict | None:
    return await database.fetchrow(
        """
        insert into human_takeovers
            (conversation_id, operator_name, status, is_test_data, is_demo, environment, created_by_seed)
        values ($1, $2, 'active', false, false, 'dev', false)
        returning id, conversation_id, operator_name, status, started_at, ended_at, notes,
                  is_test_data, is_demo, environment, test_scenario_id
        """,
        conversation_id,
        operator_name or "Operator",
    )


async def end(conversation_id: str) -> None:
    await database.execute(
        "update human_takeovers set status = 'ended', ended_at = now() "
        "where conversation_id = $1 and status = 'active'",
        conversation_id,
    )
