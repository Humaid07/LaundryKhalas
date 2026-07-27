"""Threaded messages on a facility issue (dev/test Supabase schema).

``sender_type`` ∈ facility | internal | system. ``is_internal`` messages are
internal-only notes that must NEVER be shown to the facility side — the facility
thread reads with ``include_internal=False``.
"""
from __future__ import annotations

from db import database

_SELECT = """
  select id, facility_issue_id, sender_type, sender_id, sender_label, message,
         attachment_urls, is_internal, created_at
    from facility_issue_messages
"""


async def list_messages(issue_id: str, *, include_internal: bool = True) -> list[dict]:
    if include_internal:
        return await database.fetch(
            _SELECT + " where facility_issue_id = $1 order by created_at asc", issue_id
        )
    return await database.fetch(
        _SELECT + " where facility_issue_id = $1 and is_internal = false "
        "order by created_at asc",
        issue_id,
    )


async def add_message(
    issue_id: str,
    sender_type: str,
    message: str,
    *,
    sender_id: str | None = None,
    sender_label: str | None = None,
    is_internal: bool = False,
) -> dict | None:
    return await database.fetchrow(
        """
        insert into facility_issue_messages
            (facility_issue_id, sender_type, sender_id, sender_label, message,
             is_internal, is_test_data, is_demo, environment, created_by_seed)
        values ($1, $2, $3, $4, $5, $6, true, false, 'dev', false)
        returning id, facility_issue_id, sender_type, sender_id, sender_label,
                  message, attachment_urls, is_internal, created_at
        """,
        issue_id, sender_type, sender_id, sender_label, message, is_internal,
    )
