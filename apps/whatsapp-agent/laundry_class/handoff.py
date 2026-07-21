"""Human-handoff detection and the administrator notification (task Part 6).

Deterministic: a handoff is required for refund/damage/missing-item/payment-dispute
complaints, explicit human requests, special-care items needing confirmation,
hazardous/biohazard items, threats/legal complaints, angry customers, and after three
consecutive fallback replies. The agent never resolves these itself, never promises a
refund/compensation, and never admits liability — it records the case and notifies a
human. The notification is emitted once per case (guarded by state.handoff_notified).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from laundry_class import intents as I

PENDING = "pending"
ASSIGNED = "assigned"
RESOLVED = "resolved"


@dataclass(frozen=True)
class HandoffDecision:
    required: bool
    reason: str | None = None
    priority: str = "Normal"  # High | Medium | Normal


_ANGER = re.compile(
    r"\b(angry|furious|fed up|worst|terrible|awful|unacceptable|disgusting|"
    r"ridiculous|never again|so bad|very bad|horrible)\b",
    re.IGNORECASE,
)
_THREAT = re.compile(
    r"\b(sue|lawyer|legal action|take you to court|police|report you|consumer protection|"
    r"lawsuit|attorney)\b",
    re.IGNORECASE,
)
_HAZARD = re.compile(
    r"\b(biohazard|hazardous|fuel|paint thinner|chemical|blood|contaminated)\b",
    re.IGNORECASE,
)
_MANUAL_REVIEW_ITEM = re.compile(
    r"\b(wedding dress|wedding gown|leather|suede|fur|luxury handbag|designer bag)\b",
    re.IGNORECASE,
)

# Intent -> (reason, priority). These intents always hand off.
_INTENT_HANDOFF = {
    I.REFUND: ("Refund request", "High"),
    I.DAMAGE: ("Damage complaint", "High"),
    I.MISSING_ITEM: ("Missing or lost item", "High"),
    I.HUMAN_SUPPORT: ("Customer requested a human agent", "Medium"),
}

_FALLBACK_THRESHOLD = 3


def decide(intent: str, text: str, *, fallback_streak: int = 0, payment_dispute: bool = False) -> HandoffDecision:
    """Return whether this turn requires a human handoff, with reason + priority."""
    if _THREAT.search(text):
        return HandoffDecision(True, "Threat or legal complaint", "High")
    if _HAZARD.search(text):
        return HandoffDecision(True, "Hazardous or biohazard item", "High")

    if intent in _INTENT_HANDOFF:
        reason, priority = _INTENT_HANDOFF[intent]
        return HandoffDecision(True, reason, priority)

    if intent == I.PAYMENT and (payment_dispute or _is_payment_dispute(text)):
        return HandoffDecision(True, "Payment dispute", "High")

    if _MANUAL_REVIEW_ITEM.search(text):
        return HandoffDecision(True, "Special-care item requires confirmation", "Medium")

    if _ANGER.search(text):
        return HandoffDecision(True, "Angry or dissatisfied customer", "High")

    if fallback_streak >= _FALLBACK_THRESHOLD:
        return HandoffDecision(True, "Repeated failure to understand the customer", "Medium")

    return HandoffDecision(False)


def _is_payment_dispute(text: str) -> bool:
    lowered = text.lower()
    return any(
        p in lowered for p in (
            "charged twice", "double charged", "charged me twice", "overcharged",
            "paid but", "payment failed", "wrong amount", "didn't receive", "not found",
        )
    )


def format_admin_notification(
    *,
    priority: str,
    reason: str,
    customer_name: str | None,
    phone: str,
    order_id: str | None,
    customer_message: str,
    summary: str,
    required_action: str = "Review the case and contact the customer.",
) -> str:
    """Structured administrator notification (task Part 6 template). The team-facing
    notification includes the full phone number because it is operationally required
    to act on the case; general application logs mask it instead."""
    return (
        "Laundry Class WhatsApp Handoff\n"
        f"Priority: {priority}\n"
        f"Reason: {reason}\n"
        f"Customer: {customer_name or 'Unknown'}\n"
        f"Phone: {phone}\n"
        f"Order: {order_id or 'Not provided'}\n"
        "Customer message:\n"
        f"“{customer_message}”\n"
        "Conversation summary:\n"
        f"{summary}\n"
        "Required action:\n"
        f"{required_action}"
    )
