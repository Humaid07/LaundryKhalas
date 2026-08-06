"""Customer-feedback events + review actions + global rule-change candidates.

Feedback is CAPTURED here (idempotent per provider message + type); it never
auto-changes behaviour. Global feedback is queued for Operations review; only an
authorized action promotes it to a customer-memory write or a versioned rule-change
candidate (services/customer_feedback_service.py).
"""
from __future__ import annotations

from db import database

_COLS = (
    "id, customer_id, conversation_id, order_id, order_item_id, feedback_type, scope, "
    "affected_service, affected_reply, raw_text, provider, provider_message_id, status, created_at"
)


def to_read(row: dict | None) -> dict | None:
    if not row:
        return None
    d = dict(row)
    for k in ("id", "customer_id", "conversation_id", "order_id"):
        if d.get(k) is not None:
            d[k] = str(d[k])
    return d


async def create(
    *, customer_id: str | None, feedback_type: str, scope: str,
    conversation_id: str | None = None, order_id: str | None = None, order_item_id: str | None = None,
    affected_service: str | None = None, affected_reply: str | None = None,
    raw_text: str | None = None, provider: str | None = None, provider_message_id: str | None = None,
) -> dict | None:
    """Idempotent by (provider, provider_message_id, feedback_type). A duplicate
    webhook/message never creates a second feedback event."""
    row = await database.fetchrow(
        f"""
        insert into customer_feedback_events
            (customer_id, conversation_id, order_id, order_item_id, feedback_type, scope,
             affected_service, affected_reply, raw_text, provider, provider_message_id, status, is_test_data)
        values ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,'new',false)
        on conflict (provider, provider_message_id, feedback_type)
          where provider is not null and provider_message_id is not null do nothing
        returning {_COLS}
        """,
        customer_id, conversation_id, order_id, order_item_id, feedback_type, scope,
        affected_service, affected_reply, raw_text, provider, provider_message_id,
    )
    return to_read(row)


async def list_for_review(status: str | None = None, limit: int = 100) -> list[dict]:
    if status:
        rows = await database.fetch(
            f"select {_COLS} from customer_feedback_events where status = $1 "
            "order by created_at desc limit $2", status, limit)
    else:
        rows = await database.fetch(
            f"select {_COLS} from customer_feedback_events order by created_at desc limit $1", limit)
    return [to_read(r) for r in rows]


async def set_status(feedback_id: str, status: str) -> dict | None:
    row = await database.fetchrow(
        f"update customer_feedback_events set status = $2 where id = $1 returning {_COLS}",
        feedback_id, status)
    return to_read(row)


async def add_review_action(feedback_id: str, *, action: str, actor: str | None = None,
                            notes: str | None = None) -> dict | None:
    return await database.fetchrow(
        "insert into feedback_review_actions (feedback_event_id, action, actor, notes) "
        "values ($1,$2,$3,$4) returning id, feedback_event_id, action, actor, notes, created_at",
        feedback_id, action, actor, notes)


async def create_global_candidate(feedback_id: str | None, *, target: str,
                                  proposed_change: str | None = None) -> dict | None:
    return await database.fetchrow(
        "insert into global_rule_change_candidates (feedback_event_id, target, proposed_change, status) "
        "values ($1,$2,$3,'proposed') returning id, feedback_event_id, target, proposed_change, status, created_at",
        feedback_id, target, proposed_change)


async def set_candidate_status(candidate_id: str, status: str, *, approved_by: str | None = None) -> dict | None:
    return await database.fetchrow(
        "update global_rule_change_candidates set status = $2, "
        "approved_by = coalesce($3, approved_by), updated_at = now() where id = $1 "
        "returning id, feedback_event_id, target, proposed_change, status, approved_by, created_at",
        candidate_id, status, approved_by)
