"""Standalone WhatsApp Agent orchestration.

Flow: receive message -> domain guard (layer 1) -> if out of domain,
return the fixed refusal (+ main menu actions) without calling the LLM ->
otherwise resolve intent (a clicked action's id always wins over guessing
from text) -> build context (system prompt with layer-2 domain
restriction + recent history + facts) -> call llm_service for the reply
TEXT -> separately compute which interactive actions (if any) to attach,
based purely on state/intent, independent of which provider generated the
text -> log everything.
"""
from dataclasses import dataclass, field

from agents.whatsapp_agent import order_flow, tools
from agents.whatsapp_agent.actions import (
    MAIN_MENU_ACTIONS,
    SERVICE_ACTIONS,
    Action,
    actions_by_ids,
    resolve_intent_override,
)
from agents.whatsapp_agent.prompts import build_system_prompt
from llm import service as llm_service
from llm.providers.base import LLMMessage
from rules import escalation_rules
from services.domain_guard import REFUSAL_MESSAGE, Domain, classify
from services.escalation import detect_escalation

_SMALLTALK_INTENTS = {"greeting", "smalltalk_thanks", "smalltalk_farewell"}
_ORDER_FLOW_INTENTS = {"track_order_request", "cancel_order_request", "change_pickup_time_request"}
# Intents that unambiguously belong to the booking sub-flow even before any
# slot is known - anything else only enters the flow if a slot has already
# been detected (see `booking_in_progress` below), otherwise the customer
# gets the welcome menu instead of being pushed straight into "which
# service?" for a vague opener like "I need laundry" or "I need help".
_BOOKING_ENTRY_INTENTS = {
    "new_pickup_request", "pricing_question", "service_question",
    "area_question", "confirmation_yes",
}


@dataclass
class AgentReply:
    text: str
    domain: str
    intent: str
    provider: str
    model: str
    success: bool
    latency_ms: float
    error_message: str | None
    actions: list[Action] = field(default_factory=list)
    handoff: bool = False
    # Set when this turn created or touched an order behind the scenes.
    order_id: str | None = None
    order_status: str | None = None


def _build_facts(
    *, intent: str, history: list[tuple[str, str]], text: str
) -> tuple[list[str], list[Action]]:
    """Returns (facts, actions). The first fact is always "Message intent:
    <reply_intent>." where reply_intent may differ from the raw detected
    `intent` (e.g. a vague opener is steered to reuse the fixed "greeting"
    welcome text) - the raw `intent` is still what gets logged/returned on
    AgentReply for transparency.
    """
    if intent == "greeting":
        return [f"Message intent: {intent}."], MAIN_MENU_ACTIONS
    if intent in ("smalltalk_thanks", "smalltalk_farewell"):
        return [f"Message intent: {intent}."], []

    # A pending order/add-items follow-up (the agent's last message asked
    # for an Order ID, a new time, or which items) takes priority over
    # generic keyword-based intent routing. Without this, a reply like "2
    # more shirts and a blanket" would misroute as a service question
    # (because "blanket" happens to be a service keyword) instead of
    # continuing the add-items flow it's actually answering. Only a clean
    # smalltalk/explicit-new-command reset breaks out of it.
    pending_action = tools.pending_order_action(history)
    _HARD_RESET_INTENTS = _SMALLTALK_INTENTS | {"confirmation_no"} | _ORDER_FLOW_INTENTS | {
        "add_items_request", "call_support_request",
    }

    effective_intent = intent
    if pending_action and intent not in _HARD_RESET_INTENTS:
        effective_intent = pending_action

    if effective_intent in _ORDER_FLOW_INTENTS:
        order_id = tools.extract_order_id(text)
        fact = (
            f"Order-flow action: {effective_intent}. "
            f"Order ID provided this turn: {order_id or 'not given yet'}."
        )
        if effective_intent == "change_pickup_time_request":
            new_time = tools.extract_time_hint(text)
            fact += f" New pickup time provided this turn: {new_time or 'not given yet'}."
        return [f"Message intent: {intent}.", fact], []

    if effective_intent == "add_items_request":
        items = text if effective_intent != intent else None  # only set on the follow-up turn
        fact = (
            "Order-flow action: add_items_request. "
            f"Items described this turn: {items or 'not given yet'}."
        )
        return [f"Message intent: {intent}.", fact], []

    if intent == "call_support_request":
        return [f"Message intent: {intent}."], []

    # Everything else: either a clear booking-flow intent, or a vague/
    # generic message that only enters the booking flow if some slot is
    # already known from earlier in this same conversation.
    slots = tools.accumulate_slots(history, text)
    booking_in_progress = bool(slots["service_type"] or slots["area"] or slots["time_hint"])

    if intent not in _BOOKING_ENTRY_INTENTS and not booking_in_progress:
        # unknown_laundry_related, unanswerable_question, and anything else
        # genuinely unclear or exploratory ("I need help", "What services
        # do you offer?") - steer the reply text to reuse the fixed
        # greeting/welcome copy plus the main menu, rather than a dead-end
        # non-answer or jumping straight into slot collection.
        return [f"Message intent: {intent}. Reply as: greeting."], MAIN_MENU_ACTIONS

    missing = [
        name
        for name, value in (
            ("service", slots["service_type"]),
            ("area", slots["area"]),
            ("time", slots["time_hint"]),
        )
        if not value
    ]
    facts = [
        f"Message intent: {intent}.",
        "Booking slots collected so far across this whole conversation "
        f"(not just this message) — service: {slots['service_type'] or 'not given yet'}; "
        f"area: {slots['area'] or 'not given yet'}; "
        f"time: {slots['time_hint'] or 'not given yet'}; "
        f"still missing: {', '.join(missing) if missing else 'none - all details collected'}.",
    ]
    if intent == "pricing_question" and slots["service_type"]:
        from rules import service_by_id

        service = service_by_id(slots["service_type"])
        price = tools.lookup_price(slots["service_type"])
        # Services priced only after inspection/measurement (bag spa, tailoring,
        # carpet/curtain) must NOT be auto-quoted an exact total — the team
        # confirms after seeing the item (CLAUDE.md RULE 7/8), even though a
        # 'from' starting price exists on the website.
        if service and service.get("requires_manual_quote"):
            facts.append(
                f"{slots['service_type']} is priced after inspection/measurement - do NOT "
                "quote an exact figure; tell the customer the team will confirm the exact price."
            )
        elif price:
            facts.append(
                f"Known price for {slots['service_type']}: {price['price']} {price['currency']} "
                f"per {price['unit']} (minimum {price['min_price']} {price['currency']})."
            )
        else:
            facts.append(
                f"No configured price exists yet for {slots['service_type']} - do not invent "
                "one, tell the customer the team will confirm the exact price."
            )

    actions = SERVICE_ACTIONS if "service" in missing else []
    return facts, actions


async def handle_message(
    *,
    text: str,
    history: list[tuple[str, str]],
    action_id: str | None = None,
    db=None,
    conversation=None,
) -> AgentReply:
    """history is a list of (role, text) tuples, oldest first, role in
    {"customer", "agent"} - already-persisted prior turns for this
    conversation, used to keep multi-turn context (e.g. slot filling).
    action_id, if set, is the id of the interactive button the customer
    clicked - it overrides text-based intent guessing entirely, since we
    already know exactly what they meant.

    db + conversation, when provided, enable the stateful order flows
    (booking/track/cancel/change/add) to read and mutate the mock order
    store behind the scenes. Without them the agent still replies, but the
    order-state side effects are skipped (e.g. pure unit context).
    """
    domain = classify(text)

    if domain is Domain.OUT_OF_DOMAIN:
        return AgentReply(
            text=REFUSAL_MESSAGE,
            domain=domain.value,
            intent="out_of_domain",
            provider="none",
            model="none",
            success=True,
            latency_ms=0.0,
            error_message=None,
            actions=MAIN_MENU_ACTIONS,
        )

    # RULE 6 — hand high-risk topics (complaint, refund, damage, missing item,
    # late delivery, payment, B2B, legal/safety, anger) to the human team
    # deterministically: no LLM call, no autonomous resolution/refund/promise.
    # A clicked quick action is a structured safe flow, so it is never treated
    # as an escalation (cancel/track/reschedule handle their own safe handoff).
    if action_id is None:
        category = detect_escalation(text)
        if category:
            handoff_domain = (
                domain.value if domain is Domain.IN_DOMAIN else Domain.UNCERTAIN.value
            )
            return AgentReply(
                text=escalation_rules()["handoff_message"],
                domain=handoff_domain,
                intent=f"escalation_{category}",
                provider="none",
                model="none",
                success=True,
                latency_ms=0.0,
                error_message=None,
                actions=actions_by_ids(escalation_rules().get("attach_actions", [])),
                handoff=True,
            )

    intent = resolve_intent_override(action_id) or tools.detect_intent(text)
    reply_domain = domain.value if domain is Domain.IN_DOMAIN else Domain.UNCERTAIN.value

    # Stateful order flows: booking/track/cancel/change/add read+mutate the
    # mock order store and return a deterministic, demo-honest reply. This is
    # what makes the conversation update real order state behind the scenes,
    # instead of only generating chat text. Returns None for non-order turns,
    # which then fall through to the normal LLM(mock) reply path below.
    if db is not None and conversation is not None:
        outcome = await order_flow.handle(
            db, conversation, intent=intent, action_id=action_id, text=text, history=history
        )
        if outcome is not None:
            return AgentReply(
                text=outcome.text,
                domain=reply_domain,
                intent=intent,
                provider="mock",
                model="mock-1",
                success=True,
                latency_ms=0.0,
                error_message=None,
                actions=outcome.actions,
                order_id=outcome.order_id,
                order_status=outcome.order_status,
            )

    facts, actions = _build_facts(intent=intent, history=history, text=text)

    messages = [
        LLMMessage(role="system", content=build_system_prompt()),
        LLMMessage(role="system", content=" ".join(facts)),
    ]
    for role, content in history[-10:]:
        messages.append(
            LLMMessage(role="user" if role == "customer" else "assistant", content=content)
        )
    messages.append(LLMMessage(role="user", content=text))

    result, latency_ms, success, error_message = await llm_service.complete(
        messages, max_tokens=200
    )

    reply_domain = domain.value if domain is Domain.IN_DOMAIN else Domain.UNCERTAIN.value
    return AgentReply(
        text=result.text,
        domain=reply_domain,
        intent=intent,
        provider=result.provider,
        model=result.model,
        success=success,
        latency_ms=latency_ms,
        error_message=error_message,
        actions=actions,
    )
