"""Facility-scoped audit trail (dev/test Supabase schema).

Every material facility change — create, update, status change, rates, quality,
services, hours — is recorded in ``facility_audit_log`` with a before/after JSON
snapshot, the actor and the source application (CLAUDE.md §10/§11: every action is
logged). Facility-level actions are not tied to an order, so this is separate from
``order_events``. Secrets/tokens are never written here (only field values).
"""
from __future__ import annotations

import json

from db import database

_COLS = (
    "id, facility_id, action, actor_id, actor_type, source_app, "
    "before_json, after_json, created_at"
)


def _dump(v) -> str | None:
    if v is None:
        return None
    # asyncpg jsonb param: encode to text and cast ::jsonb at the placeholder.
    return json.dumps(v, default=str)


async def create(
    *,
    facility_id: str | None,
    action: str,
    actor_id: str | None = None,
    actor_type: str = "internal",
    source_app: str | None = None,
    before: dict | None = None,
    after: dict | None = None,
) -> dict | None:
    return await database.fetchrow(
        f"""
        insert into facility_audit_log
            (facility_id, action, actor_id, actor_type, source_app, before_json, after_json)
        values ($1, $2, $3, $4, $5, $6::text::jsonb, $7::text::jsonb)
        returning {_COLS}
        """,
        facility_id, action, actor_id, actor_type, source_app,
        _dump(before), _dump(after),
    )


async def list_for_facility(facility_id: str, *, limit: int = 50) -> list[dict]:
    return await database.fetch(
        f"select {_COLS} from facility_audit_log where facility_id = $1 "
        f"order by created_at desc limit {int(limit)}",
        facility_id,
    )
