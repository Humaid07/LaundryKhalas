"""Deterministic escalation / human-handoff detection (RULE 6 / CLAUDE.md §6).

Keyword match against config/escalation_rules.json. On a match the agent
hands the conversation to the human LaundryKhalaas team instead of trying
to resolve it, refund, compensate, or make any promise — see
agents/whatsapp_agent/agent.py, which short-circuits (no LLM call) with the
configured handoff message.

Cancellation, reschedule and order-tracking are intentionally NOT detected
here — they are handled by their own dedicated safe quick-action flows,
which already hand off to the team without taking a real action.
"""
from rules import escalation_rules


def detect_escalation(text: str) -> str | None:
    """Returns the matched escalation category (e.g. "refund", "complaint")
    or None if the message needs no handoff."""
    if not text:
        return None
    lowered = text.lower()
    for category in escalation_rules()["categories"]:
        if any(keyword in lowered for keyword in category["keywords"]):
            return category["category"]
    return None
