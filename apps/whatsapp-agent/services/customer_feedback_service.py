"""Controlled feedback operations (spec §28/§26).

Capture feedback from a customer message (idempotent), classify scope, queue GLOBAL
feedback for authorized Operations review, and — only on approval — promote it to a
customer-memory write or a versioned global rule-change candidate. Unreviewed global
feedback NEVER changes production behaviour (no auto prompt/rule/model edit).
"""
from __future__ import annotations

from db.repositories import customer_feedback_repo as repo
from services import customer_feedback as detect
from services import customer_memory_service


async def create_customer_feedback_event(
    text: str,
    *,
    customer_id: str | None,
    conversation_id: str | None = None,
    order_id: str | None = None,
    order_item_id: str | None = None,
    provider: str | None = None,
    provider_message_id: str | None = None,
    affected_service: str | None = None,
    affected_reply: str | None = None,
) -> list[dict]:
    """Detect + persist any feedback events in a message. Global feedback lands in
    the review queue; nothing changes global behaviour automatically."""
    created: list[dict] = []
    for ev in detect.detect_feedback(text):
        row = await repo.create(
            customer_id=customer_id, feedback_type=ev["feedback_type"], scope=ev["scope"],
            conversation_id=conversation_id, order_id=order_id, order_item_id=order_item_id,
            affected_service=affected_service, affected_reply=affected_reply, raw_text=text,
            provider=provider, provider_message_id=provider_message_id)
        if row:  # None = idempotent duplicate
            created.append(row)
    return created


def classify_feedback_scope(feedback_type: str, text: str) -> str:
    return detect.classify_scope(feedback_type, text)


async def queue_global_feedback_review(feedback_id: str, *, target: str,
                                       proposed_change: str | None = None) -> dict | None:
    """Create a versioned rule-change CANDIDATE for authorized review (never applied)."""
    await repo.set_status(feedback_id, "reviewed")
    return await repo.create_global_candidate(feedback_id, target=target, proposed_change=proposed_change)


async def approve_feedback_as_customer_memory(
    feedback_id: str, *, customer_id: str, memory_type: str, memory_key: str, memory_value,
    scope: str, actor: str | None = None,
) -> dict:
    """Operations promotes a customer-scoped feedback into durable memory."""
    result = await customer_memory_service.save_confirmed_customer_memory(
        customer_id, memory_type=memory_type, memory_key=memory_key, memory_value=memory_value,
        scope=scope, customer_confirmed=True)
    await repo.add_review_action(feedback_id, action="approve_customer_memory", actor=actor)
    await repo.set_status(feedback_id, "approved")
    return result


async def approve_feedback_rule_change(candidate_id: str, *, approved_by: str) -> dict | None:
    """Approve a GLOBAL rule-change candidate (still deployed through the normal
    versioned config process — this does not itself edit prompts/rules)."""
    return await repo.set_candidate_status(candidate_id, "approved", approved_by=approved_by)


async def reject_feedback(feedback_id: str, *, actor: str | None = None, duplicate: bool = False) -> dict | None:
    await repo.add_review_action(feedback_id, action="duplicate" if duplicate else "reject", actor=actor)
    return await repo.set_status(feedback_id, "duplicate" if duplicate else "rejected")
