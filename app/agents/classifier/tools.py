"""Deterministic classification logic for the Classifier Agent.

Mirrors the pattern already used by `app.agents.whatsapp_operations.tools
.extract_order_slots`: keyword/pattern matching over message text, never an
LLM call reasoning freely over facts. Classification labels aren't
"invented data" in the CLAUDE.md sense (there's no wrong price or policy to
fabricate here), but staying deterministic keeps this testable and
consistent with the rest of the codebase's mock-first design, and mirrors
exactly what would need to change to swap in a real LLM later: only the
call inside `agent.py` that currently logs this dict through
`llm_service.complete()`, not the calling code around it.

Taxonomy and routing rules are adapted from the old prototype's Section D.4
classifier spec (`docs/agents/Classifier-D4.md`,
`docs/specs/00-master-build-spec.md` in `LaundryKhalaasPrototype`), reviewed
and referenced as a starting point in `docs/audits/prototype-md-review.md`.
Not copied verbatim - the sentiment scale and routing thresholds are
adapted here (see below).
"""
from __future__ import annotations

INTENTS: tuple[str, ...] = (
    "new_enquiry",
    "quote_request",
    "order_placement",
    "order_tracking",
    "complaint",
    "pickup_issue",
    "delivery_issue",
    "payment_issue",
    "facility_issue",
    "pricing_objection",
    "cancellation",
    "rescheduling",
    "b2b_lead",
    "facility_onboarding",
    "driver_support",
    "lost_lead",
    "repeat_order",
    "general_enquiry",
)

SENTIMENTS: tuple[str, ...] = ("happy", "neutral", "frustrated", "urgent", "angry")

SALES_STAGES: tuple[str, ...] = (
    "new_lead",
    "qualified",
    "quoted",
    "follow_up_needed",
    "won",
    "lost",
    "no_change",
)

# Ordered so the first matching intent wins - most specific/urgent first.
_INTENT_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("cancellation", ("cancel my order", "cancel it", "want to cancel", "cancel the")),
    ("rescheduling", ("reschedule", "change the pickup time", "change the time", "move my pickup")),
    ("payment_issue", ("payment failed", "card declined", "charged twice", "double charged", "refund")),
    ("pickup_issue", ("driver never came", "pickup was late", "no one showed up", "missed my pickup")),
    ("delivery_issue", ("delivery is late", "haven't received my delivery", "still not delivered")),
    ("facility_issue", ("damaged", "stained", "ruined", "missing item", "lost my clothes", "poor quality")),
    ("complaint", ("terrible", "worst", "unacceptable", "disgusted", "ridiculous", "very unhappy")),
    ("order_tracking", ("where is my order", "track my order", "order status", "is my order ready")),
    ("pricing_objection", ("too expensive", "too pricey", "price is high", "can you lower", "cheaper")),
    ("quote_request", ("how much", "what's the price", "what is the price", "get a quote", "cost of")),
    ("b2b_lead", ("bulk order", "corporate account", "hotel contract", "business account", "b2b")),
    ("facility_onboarding", ("become a partner", "partner facility", "list our facility")),
    ("driver_support", ("become a driver", "driver job", "delivery job application")),
    ("repeat_order", ("same as last time", "reorder", "usual order", "repeat my last order")),
    ("order_placement", ("pickup tomorrow", "pickup today", "need laundry", "book a pickup", "schedule a pickup")),
)

_SENTIMENT_KEYWORDS: tuple[tuple[str, tuple[str, ...], float], ...] = (
    ("angry", ("furious", "unacceptable", "disgusted", "ridiculous", "worst service", "terrible"), -0.9),
    ("frustrated", ("frustrated", "annoyed", "not happy", "disappointed", "again and again"), -0.5),
    ("urgent", ("urgent", "asap", "right now", "emergency", "immediately"), -0.2),
    ("happy", ("thank you", "thanks", "great", "awesome", "perfect", "love it", "appreciate"), 0.8),
)

_URGENT_INTENTS = {"complaint", "pickup_issue", "delivery_issue", "payment_issue", "facility_issue"}
_FOLLOWUP_INTENTS = {"quote_request", "pricing_objection", "order_placement", "b2b_lead"}
_COMPLAINT_INTENTS = _URGENT_INTENTS
_REFUND_CANCELLATION_INTENTS = {"cancellation", "payment_issue"}
_B2B_INTENTS = {"b2b_lead", "facility_onboarding"}

_SALES_STAGE_BY_INTENT: dict[str, str] = {
    "new_enquiry": "new_lead",
    "general_enquiry": "new_lead",
    "quote_request": "quoted",
    "order_placement": "won",
    "repeat_order": "won",
    "complaint": "follow_up_needed",
    "pickup_issue": "follow_up_needed",
    "delivery_issue": "follow_up_needed",
    "payment_issue": "follow_up_needed",
    "facility_issue": "follow_up_needed",
    "pricing_objection": "follow_up_needed",
    "cancellation": "lost",
    "lost_lead": "lost",
    "b2b_lead": "qualified",
    "facility_onboarding": "qualified",
    "driver_support": "qualified",
}


def classify_text(text: str, *, is_first_message: bool = False) -> dict:
    """Deterministic classification of a single message's text.

    Returns the four Section-D.4-shaped fields: intent, sentiment,
    sentiment_score (-1.0..+1.0), sales_stage_delta, topic.
    """
    lowered = text.lower()

    intent = "general_enquiry"
    matched_phrase: str | None = None
    for candidate_intent, phrases in _INTENT_KEYWORDS:
        hit = next((p for p in phrases if p in lowered), None)
        if hit:
            intent = candidate_intent
            matched_phrase = hit
            break
    if intent == "general_enquiry" and is_first_message:
        intent = "new_enquiry"

    sentiment = "neutral"
    sentiment_score = 0.0
    for candidate_sentiment, phrases, score in _SENTIMENT_KEYWORDS:
        if any(p in lowered for p in phrases):
            sentiment = candidate_sentiment
            sentiment_score = score
            break

    sales_stage_delta = _SALES_STAGE_BY_INTENT.get(intent, "no_change")

    topic = matched_phrase if matched_phrase else intent.replace("_", " ")

    return {
        "intent": intent,
        "sentiment": sentiment,
        "sentiment_score": sentiment_score,
        "sales_stage_delta": sales_stage_delta,
        "topic": topic,
    }


def compute_routing_flags(classification: dict) -> dict:
    """Routing flags per CLAUDE.md §9's classifier responsibilities list,
    adapted from the prototype's `_apply_routing_rules` thresholds (which
    used a 0.0-1.0 sentiment scale) to this module's -1.0..+1.0 scale.
    """
    intent = classification["intent"]
    sentiment = classification["sentiment"]
    score = classification["sentiment_score"]

    is_urgent = intent in _URGENT_INTENTS or sentiment == "angry"
    is_escalated = score <= -0.5
    if score <= -0.8:
        is_urgent = True

    return {
        "is_urgent": is_urgent,
        "is_escalated": is_escalated,
        "needs_followup": intent in _FOLLOWUP_INTENTS,
        "complaint_flag": intent in _COMPLAINT_INTENTS,
        "angry_flag": sentiment == "angry",
        "refund_or_cancellation_detected": intent in _REFUND_CANCELLATION_INTENTS,
        "b2b_enquiry_detected": intent in _B2B_INTENTS,
    }


def latest_urgency_label(flags: dict) -> str:
    """Collapses the flag set into the single `Conversation.latest_urgency`
    placeholder column (String(32), free-form). The full flag set lives in
    the AIActionLog audit record, not this column - see
    docs/architecture/classifier-agent.md.
    """
    if flags["is_urgent"]:
        return "urgent"
    if flags["is_escalated"]:
        return "escalated"
    return "normal"
