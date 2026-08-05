"""Deterministic pre-classification — never spend an LLM call on what code can
decide reliably (spec: "Deterministic handling before the LLM classifier").

``preclassify`` inspects the compact ``ClassifierInput`` plus known signals and,
when the turn is unambiguous, returns a terminal ``DeterministicResult`` carrying
a fully-formed ``Classification`` (status=DETERMINISTIC). The LLM classifier is
skipped entirely for those. Otherwise it returns ``None`` and the caller runs the
model.

IMPORTANT: this layer only handles events that are genuinely unambiguous from
structure/keywords (location pin, known interactive payload, exact opt-out,
explicit human request). Everything requiring language understanding falls
through to the model. Operational gates that already run BEFORE the classifier
hook in the webhook (duplicate/fromMe/status/paused/takeover/voice) are NOT
re-implemented here — they never reach this function.
"""
from __future__ import annotations

from dataclasses import dataclass

from classifier.context import ClassifierInput
from classifier.schema import Classification, ClassifierStatus

# Exact opt-out keywords (compared case-insensitively against the trimmed whole
# message only — never a substring, so "stop by at 5pm" is NOT an opt-out).
OPT_OUT_KEYWORDS: frozenset[str] = frozenset({
    "stop", "unsubscribe", "cancel subscription", "opt out", "optout",
    "remove me", "do not message me", "don't message me", "leave me alone",
})

# Explicit human/agent requests handled deterministically (whole-phrase or clear
# substring). The model still catches subtler phrasings; these are the certain ones.
HUMAN_REQUEST_PHRASES: tuple[str, ...] = (
    "speak to a human", "talk to a human", "speak to an agent", "talk to an agent",
    "speak to a manager", "talk to a manager", "speak to a person", "real person",
    "human agent", "customer service representative", "connect me to support",
)
HUMAN_REQUEST_REASONS = {
    "manager": "CUSTOMER_REQUESTED_MANAGER",
    "supervisor": "CUSTOMER_REQUESTED_SUPERVISOR",
    "operations": "CUSTOMER_REQUESTED_OPERATIONS",
}


@dataclass
class DeterministicResult:
    is_terminal: bool
    classification: Classification | None = None
    reason: str = ""


def _terminal(classification: Classification, reason: str) -> DeterministicResult:
    classification.status = ClassifierStatus.DETERMINISTIC
    return DeterministicResult(is_terminal=True, classification=classification, reason=reason)


def preclassify(ci: ClassifierInput) -> DeterministicResult:
    """Return a terminal result when the turn is unambiguous, else non-terminal."""
    msg = ci.message
    sig = ci.known_signals
    convo = ci.conversation
    text = (msg.text or "").strip()
    lowered = text.lower()

    # 1) Location pin event → LOCATION_PIN_PROVIDED (never ask the model "is this
    #    a location?"). The backend still resolves the actual coordinates.
    if msg.has_location or msg.message_type == "location":
        return _terminal(
            Classification(
                primary_intent="LOCATION_PIN_PROVIDED",
                intent_confidence=1.0,
                service_domain=convo.selected_service or "UNKNOWN",
                customer_goal="PROVIDE_INFORMATION",
                conversation_route="OPERATIONS_EVENT",
                should_cancel_followups=True,
                reason_codes=["LOCATION_EVENT", "DETERMINISTIC_EVENT"],
            ),
            reason="location_event",
        )

    # 2) Known interactive selection (pickup-slot / order button / payment button)
    #    with a stable payload/id → resolve to selection, backend maps the id.
    if sig.exact_button_payload or sig.known_selection_id:
        intent = "PICKUP_SLOT_SELECTION" if convo.has_active_slot_options else "ORDER_CONFIRMATION"
        return _terminal(
            Classification(
                primary_intent=intent,
                intent_confidence=1.0,
                service_domain=convo.selected_service or "UNKNOWN",
                customer_goal="CONTINUE_ORDER",
                conversation_route="DETERMINISTIC_HANDLER",
                should_cancel_followups=True,
                reason_codes=["SLOT_SELECTION_IN_CONTEXT", "DETERMINISTIC_EVENT"],
            ),
            reason="known_interactive_payload",
        )

    # 3) Exact opt-out keyword (whole-message match only).
    if sig.deterministic_opt_out or lowered in OPT_OUT_KEYWORDS:
        return _terminal(
            Classification(
                primary_intent="OPT_OUT",
                intent_confidence=1.0,
                customer_goal="END_CONVERSATION",
                conversation_route="DETERMINISTIC_HANDLER",
                fixed_template_id="OPT_OUT_CONFIRMATION",
                should_cancel_followups=True,
                reason_codes=["OPT_OUT_KEYWORD", "DETERMINISTIC_EVENT"],
            ),
            reason="opt_out",
        )

    # 4) Explicit human/agent request → mandatory human intervention. (The model
    #    still catches subtler asks; this covers the unambiguous phrasings so we
    #    never miss an explicit "get me a manager".)
    if sig.deterministic_human_request or any(p in lowered for p in HUMAN_REQUEST_PHRASES):
        reason = "CUSTOMER_REQUESTED_HUMAN"
        for kw, r in HUMAN_REQUEST_REASONS.items():
            if kw in lowered:
                reason = r
                break
        return _terminal(
            Classification(
                primary_intent="HUMAN_AGENT_REQUEST",
                intent_confidence=1.0,
                customer_goal="REQUEST_HUMAN",
                conversation_route="HUMAN_INTERVENTION",
                requires_human=True,
                human_reason=reason,
                fixed_template_id="HUMAN_HANDOVER",
                should_cancel_followups=True,
                reason_codes=["HUMAN_REQUEST_PHRASE", "DETERMINISTIC_EVENT"],
            ),
            reason="human_request",
        )

    # 5) Empty / content-free turn with no signal → nothing to classify.
    if not text and not (msg.has_image or msg.has_audio):
        return _terminal(
            Classification(
                primary_intent="UNKNOWN",
                intent_confidence=0.0,
                conversation_route="IGNORE",
                should_cancel_followups=False,
                reason_codes=["DETERMINISTIC_EVENT"],
            ),
            reason="empty_turn",
        )

    return DeterministicResult(is_terminal=False)
