"""Silent human conversion review (spec §9 / §18).

When the deterministic discount engine says nothing more may be offered (ceiling /
margin floor) and the customer keeps objecting, the agent must NOT invent an offer.
Instead a CUSTOMER_CONVERSION_REVIEW pending task is created for the team, carrying
the internal commercial context. This does NOT pause the bot and the customer is not
told they were escalated (that only happens on a real human takeover). At most one
open review per conversation (dedupe), so a stalling conversation never spawns
duplicate cases.
"""
from __future__ import annotations

TASK_TYPE = "CUSTOMER_CONVERSION_REVIEW"

# Fields surfaced to the reviewer (internal only — never shown to the customer).
_ORDER = [
    ("service", "Service"),
    ("current_price", "Current customer price"),
    ("existing_discount", "Existing discount"),
    ("max_discount", "Max permissible discount"),
    ("facility_cost", "Facility cost"),
    ("hesitation", "Hesitation reason"),
    ("state", "Conversation state"),
]


def build_review_notes(reason: str, context: dict) -> str:
    """Format the internal review context as human-readable notes."""
    lines = [f"Reason: {reason}"]
    for key, label in _ORDER:
        if context.get(key) not in (None, ""):
            lines.append(f"{label}: {context[key]}")
    msgs = context.get("recent_messages")
    if msgs:
        joined = " | ".join(str(m) for m in msgs)
        lines.append(f"Recent customer messages: {joined}")
    return "\n".join(lines)


async def flag_conversion_review(*, conversation_id, reason, context: dict,
                                 customer_id=None, order_id=None, repo=None) -> bool:
    """Create a silent conversion-review task if none is open for this conversation.

    Returns True if a task was created, False if one was already open (deduped).
    ``repo`` must expose ``has_open(conversation_id, task_type)`` and ``create(...)``;
    it defaults to the durable pending-tasks repo.
    """
    if repo is None:
        from db.repositories import pending_tasks_repo as repo  # noqa: N813
    if await repo.has_open(conversation_id, TASK_TYPE):
        return False
    await repo.create(
        TASK_TYPE, conversation_id=conversation_id, customer_id=customer_id,
        order_id=order_id, notes=build_review_notes(reason, context))
    return True
