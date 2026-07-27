"""Complaint classification + empathetic acknowledgement (pure, deterministic).

Turns an escalation into a structured complaint category and composes a safe,
empathetic acknowledgement. The agent NEVER argues, defends a facility, or
promises a refund/replacement/compensation (CLAUDE.md §6) — it apologises, asks
only for the genuinely missing detail (order reference / photo), and hands off to
Operations. All functions here are pure and side-effect free; persistence lives in
``db/repositories/complaints_repo.py``.
"""
from __future__ import annotations

# Structured complaint categories (also the DB `complaints.category` domain).
CATEGORIES = (
    "delay_collection", "delay_delivery", "poor_cleaning", "poor_pressing",
    "shrinking", "damage", "missing_items", "damp", "incorrect_alteration",
    "refund_request", "reprocessing", "facility_disagreement", "other",
)

# Coarse mapping from the escalation detector's category → complaint category.
_ESCALATION_TO_CATEGORY = {
    "refund": "refund_request",
    "damaged_item": "damage",
    "missing_item": "missing_items",
    "late_delivery": "delay_delivery",
    "payment_issue": "other",
    "complaint": "other",
    "angry": "other",
}

# Keyword refinement (checked first — more specific than the coarse map).
_KEYWORD_CATEGORY: tuple[tuple[tuple[str, ...], str], ...] = (
    (("shrunk", "shrank", "shrink", "smaller now"), "shrinking"),
    (("damp", "still wet", "wet clothes", "moist", "smell"), "damp"),
    (("torn", "ripped", "tear", "damaged", "broke", "stretched", "hole", "burn"), "damage"),
    (("missing", "lost item", "not returned", "one shirt short", "item missing"), "missing_items"),
    (("not clean", "still dirty", "stain", "dirty", "not properly cleaned"), "poor_cleaning"),
    (("not pressed", "not ironed", "wrinkled", "creased", "badly pressed"), "poor_pressing"),
    (("too short", "wrong size", "alteration wrong", "hem is", "doesn't fit", "does not fit"), "incorrect_alteration"),
    (("redo", "re-do", "reprocess", "clean again", "do it again", "wash again"), "reprocessing"),
    (("not collected", "no pickup", "didn't collect", "did not collect", "late pickup", "late collection"), "delay_collection"),
    (("not delivered", "late delivery", "where is my", "still not received", "delayed delivery"), "delay_delivery"),
    (("refund", "money back", "compensate", "compensation"), "refund_request"),
)

# Requested resolution detection.
_RESOLUTION_KEYWORDS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("refund", "money back"), "refund"),
    (("replace", "replacement", "new one"), "replacement"),
    (("redo", "reprocess", "clean again", "wash again", "it again", "re-clean", "reclean"), "reclean"),
)

_PRIORITY_TO_URGENCY = {
    "urgent": "urgent", "high": "high", "medium": "medium", "low": "low",
}


def classify_category(text: str | None, escalation_category: str | None = None) -> str:
    """Best complaint category from the message text, falling back to the coarse
    escalation-category map, else 'other'."""
    t = (text or "").lower()
    for keywords, category in _KEYWORD_CATEGORY:
        if any(k in t for k in keywords):
            return category
    if escalation_category:
        return _ESCALATION_TO_CATEGORY.get(escalation_category, "other")
    return "other"


def detect_requested_resolution(text: str | None) -> str:
    t = (text or "").lower()
    for keywords, resolution in _RESOLUTION_KEYWORDS:
        if any(k in t for k in keywords):
            return resolution
    return "unknown"


def urgency_from_priority(priority: str | None) -> str:
    return _PRIORITY_TO_URGENCY.get((priority or "").lower(), "medium")


def empathetic_ack(category: str, *, has_order_ref: bool, has_photo: bool) -> str:
    """A single empathetic acknowledgement that asks ONLY for the missing detail.
    Never promises a refund, replacement or compensation."""
    opener = "I'm really sorry about this — that's not the experience we want you to have."
    handoff = "I've flagged it to our Operations team so they can look into it right away."

    needs = []
    if not has_order_ref:
        needs.append("your order reference")
    if not has_photo and category in (
        "damage", "poor_cleaning", "poor_pressing", "shrinking", "damp",
        "incorrect_alteration", "missing_items",
    ):
        needs.append("a photo of the affected item")

    if needs:
        if len(needs) == 2:
            ask = f"To help them act quickly, could you share {needs[0]} and {needs[1]}?"
        else:
            ask = f"To help them act quickly, could you share {needs[0]}?"
        return f"{opener} {handoff} {ask}"
    return f"{opener} {handoff} They'll review the details and get back to you shortly."
