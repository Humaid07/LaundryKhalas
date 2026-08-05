"""WhatsApp intent classifier — unit + integration tests.

Runs entirely offline: conftest forces LLM_PROVIDER=mock, so classify_turn takes
the deterministic rule-engine path (no live Anthropic key, no token spend). The
live Sonnet-5 path is exercised separately (see the eval harness, deferred); here
we lock down the taxonomy, deterministic pre-classification, routing, lifecycle,
schema validation, confidence policy, and mandatory human-escalation recall.
"""
from __future__ import annotations

import pytest

from classifier import deterministic, rule_engine, taxonomy as tax
from classifier.context import (
    ClassifierInput,
    ConversationInput,
    KnownSignals,
    MessageInput,
    RecentContextItem,
)
from classifier.lifecycle import LifecycleFacts, resolve_lifecycle
from classifier.router import select_route
from classifier.schema import (
    CLASSIFIER_TOOL_SCHEMA,
    Classification,
    ClassifierStatus,
)
from classifier.service import classify_turn
from settings import get_settings


@pytest.fixture(autouse=True)
def _enable_classifier(monkeypatch):
    """conftest defaults WHATSAPP_CLASSIFIER_ENABLED=false for the rest of the
    suite; the classifier's own tests opt back in (per that contract)."""
    monkeypatch.setattr(get_settings(), "whatsapp_classifier_enabled", True)


def ci(text: str, *, assistant: str | None = None, **conv) -> ClassifierInput:
    recent = [RecentContextItem(role="assistant", text=assistant)] if assistant else []
    return ClassifierInput(
        message=MessageInput(text=text),
        conversation=ConversationInput(**conv),
        recent_context=recent,
    )


# ---------------------------------------------------------------------------
# Primary-intent coverage (the spec's "Required tests")
# ---------------------------------------------------------------------------
PRIMARY_CASES = {
    "Hi": "GREETING",
    "What services do you provide?": "SERVICE_ENQUIRY",
    "I need wash and fold.": "SERVICE_SELECTION",
    "I only need ironing.": "SERVICE_SELECTION",
    "How much for 8 kg wash and fold?": "PRICE_ENQUIRY",
    "That is too expensive.": "PRICE_PUSHBACK",
    "Can you give me 25% off?": "DISCOUNT_REQUEST",
    "How does the process work?": "PROCESS_ENQUIRY",
    "Apartment 403, Marina Tower, floor 4.": "ADDRESS_PROVIDED",
    "What pickup times are available?": "PICKUP_SLOT_ENQUIRY",
    "Can you collect at 5 PM?": "EXACT_PICKUP_TIME_REQUEST",
    "I need a repair.": "REPAIR_REQUEST",
    "I need my trousers shortened.": "ALTERATION_REQUEST",
    "My shirt is torn and needs sewing.": "REPAIR_REQUEST",
    "My shoes need sole gluing.": "REPAIR_REQUEST",
    "My designer bag needs colour restoration.": "SPECIALIST_RESTORATION_REQUEST",
    "Can you repair my phone?": "UNSUPPORTED_REQUEST",
    "How do I pay?": "PAYMENT_METHOD_ENQUIRY",
    "Do you take cash?": "PAYMENT_METHOD_ENQUIRY",
    "I do not have Stripe.": "STRIPE_PAYMENT_QUERY",
    "I still prefer cash.": "CASH_PAYMENT_REQUEST",
    "I was charged twice.": "COMPLAINT",
    "Where is my order?": "ORDER_STATUS_ENQUIRY",
    "No one has updated me for two days.": "COMPLAINT",
    "You damaged my dress.": "COMPLAINT",
    "One shirt is missing.": "COMPLAINT",
    "I want a refund.": "REFUND_REQUEST",
    "Clean it again for free.": "REPROCESSING_REQUEST",
    "We are a hotel and need daily linen collection.": "B2B_ENQUIRY",
}


@pytest.mark.parametrize("text,expected", list(PRIMARY_CASES.items()))
def test_primary_intent(text, expected):
    c = rule_engine.classify(ci(text))
    assert c.primary_intent == expected, f"{text!r} → {c.primary_intent} (want {expected})"
    assert c.primary_intent in tax.PRIMARY_INTENTS


# ---------------------------------------------------------------------------
# Service-domain + repair rules
# ---------------------------------------------------------------------------
def test_dry_cleaning_maps_to_clean_and_press():
    c = rule_engine.classify(ci("I need dry cleaning for two shirts."))
    assert c.service_domain == "CLEAN_AND_PRESS"
    assert c.detected_entities.mentioned_quantity == 2


def test_wash_and_iron_maps_to_clean_and_press():
    assert rule_engine.classify(ci("I need wash and iron")).service_domain == "CLEAN_AND_PRESS"


def test_alteration_service_and_repair_intent():
    c = rule_engine.classify(ci("I need my trousers shortened."))
    assert c.service_domain == "ALTERATIONS_AND_GARMENT_REPAIR"
    assert c.repair_intent == "STANDARD_ALTERATION"


def test_garment_repair_intent():
    c = rule_engine.classify(ci("My shirt is torn and needs sewing."))
    assert c.service_domain == "ALTERATIONS_AND_GARMENT_REPAIR"
    assert c.repair_intent == "STANDARD_GARMENT_REPAIR"


def test_shoe_repair_intent():
    c = rule_engine.classify(ci("My shoes need sole gluing."))
    assert c.service_domain == "SHOES"
    assert c.repair_intent == "SHOE_REPAIR"


def test_bag_restoration_specialist():
    c = rule_engine.classify(ci("My designer bag needs colour restoration."))
    assert c.repair_intent == "SPECIALIST_RESTORATION"
    assert "RESTORATION" in (c.detected_entities.mentioned_services + [c.service_domain] + c.secondary_intents) \
        or c.service_domain in ("BAGS_AND_ACCESSORIES", "RESTORATION")


def test_ambiguous_repair_never_unsupported():
    c = rule_engine.classify(ci("I need a repair."))
    assert c.primary_intent == "REPAIR_REQUEST"
    assert c.repair_intent == "AMBIGUOUS_REPAIR"
    assert c.needs_clarification is True
    assert c.clarification_topic == "REPAIR_ITEM_AND_SCOPE"


def test_non_laundry_repair_is_unsupported_and_keeps_state():
    c = rule_engine.classify(ci("Can you repair my phone?", selected_service="WASH_AND_FOLD"))
    assert c.primary_intent == "UNSUPPORTED_REQUEST"
    assert "NON_LAUNDRY_REPAIR" in c.reason_codes
    assert c.repair_intent == "UNSUPPORTED_NON_LAUNDRY_REPAIR"


def test_stripe_not_misread_as_repair():
    # regression: "stripe" contains the substring "rip"
    c = rule_engine.classify(ci("I do not have Stripe."))
    assert c.primary_intent == "STRIPE_PAYMENT_QUERY"
    assert c.payment_intent == "STRIPE_ACCOUNT_CONCERN"


# ---------------------------------------------------------------------------
# Pricing / payment
# ---------------------------------------------------------------------------
def test_price_pushback_not_anger():
    c = rule_engine.classify(ci("That is too expensive."))
    assert c.primary_intent == "PRICE_PUSHBACK"
    assert c.pricing_intent == "PRICE_PUSHBACK"
    assert c.sentiment != "ANGRY"
    assert c.frustration_level == 0


def test_discount_request_no_calculation():
    c = rule_engine.classify(ci("Can you give me 25% off?"))
    assert c.primary_intent == "DISCOUNT_REQUEST"
    assert c.pricing_intent == "ASKING_DISCOUNT"


def test_cash_enquiry_template():
    c = rule_engine.classify(ci("Do you take cash?"))
    assert c.payment_intent == "CASH_ENQUIRY"
    assert c.fixed_template_id == "STRIPE_REGULAR_PAYMENT"


def test_duplicate_charge_requires_human():
    c = rule_engine.classify(ci("I was charged twice."))
    assert c.requires_human is True
    assert c.human_reason == "DUPLICATE_CHARGE"
    assert c.payment_intent == "DUPLICATE_CHARGE"


def test_price_enquiry_captures_weight_without_pricing():
    c = rule_engine.classify(ci("How much for 8 kg wash and fold?"))
    assert c.primary_intent == "PRICE_ENQUIRY"
    assert c.service_domain == "WASH_AND_FOLD"
    assert c.detected_entities.mentioned_weight_kg == 8.0


# ---------------------------------------------------------------------------
# Pickup slot context
# ---------------------------------------------------------------------------
def test_slot_selection_only_with_active_options():
    assert rule_engine.classify(ci("Option 2", has_active_slot_options=True)).primary_intent == "PICKUP_SLOT_SELECTION"
    # no active options → not a slot selection
    assert rule_engine.classify(ci("Option 2")).primary_intent != "PICKUP_SLOT_SELECTION"


def test_status_not_complaint_by_default():
    assert rule_engine.classify(ci("Where is my order?")).primary_intent == "ORDER_STATUS_ENQUIRY"


def test_no_update_is_complaint():
    c = rule_engine.classify(ci("No one has updated me for two days."))
    assert c.primary_intent == "COMPLAINT"
    assert c.complaint_type == "NO_UPDATE"


# ---------------------------------------------------------------------------
# Multi-intent
# ---------------------------------------------------------------------------
def test_multi_intent_price_pickup_payment():
    c = rule_engine.classify(ci("How much for two suits, can you collect tomorrow, and do you accept cash?"))
    assert c.primary_intent == "PRICE_ENQUIRY"
    assert c.service_domain == "SUITS_AND_BLAZERS"
    assert "PAYMENT_METHOD_ENQUIRY" in c.secondary_intents
    assert c.is_multi_intent


# ---------------------------------------------------------------------------
# Contextual short replies
# ---------------------------------------------------------------------------
def test_confirm_in_summary_context():
    c = rule_engine.classify(ci("Okay confirm", assistant="Here is your order summary, total AED 90. Confirm?"))
    assert c.primary_intent == "ORDER_CONFIRMATION"


def test_yes_reuse_address_context():
    c = rule_engine.classify(ci("Yes", assistant="Should I reuse your saved address?",
                                last_assistant_was_question=True))
    assert c.primary_intent == "BOOKING_CONTINUE"


# ---------------------------------------------------------------------------
# Deterministic pre-classification (no LLM)
# ---------------------------------------------------------------------------
def test_location_event_is_deterministic():
    ci_loc = ClassifierInput(message=MessageInput(text="", has_location=True, message_type="location"))
    r = deterministic.preclassify(ci_loc)
    assert r.is_terminal
    assert r.classification.primary_intent == "LOCATION_PIN_PROVIDED"
    assert r.classification.status == ClassifierStatus.DETERMINISTIC


def test_manager_request_is_deterministic_mandatory_human():
    r = deterministic.preclassify(ci("Let me speak to a manager."))
    assert r.is_terminal
    assert r.classification.primary_intent == "HUMAN_AGENT_REQUEST"
    assert r.classification.requires_human is True
    assert r.classification.human_reason == "CUSTOMER_REQUESTED_MANAGER"


def test_exact_optout_keyword():
    r = deterministic.preclassify(ci("stop"))
    assert r.is_terminal and r.classification.primary_intent == "OPT_OUT"
    # a sentence merely containing "stop" is NOT an opt-out
    assert not deterministic.preclassify(ci("can you stop by at 5pm")).is_terminal


def test_known_selection_payload_deterministic():
    payload = ClassifierInput(
        message=MessageInput(text="pick"),
        conversation=ConversationInput(has_active_slot_options=True),
        known_signals=KnownSignals(exact_button_payload="SLOT_2"),
    )
    r = deterministic.preclassify(payload)
    assert r.is_terminal and r.classification.primary_intent == "PICKUP_SLOT_SELECTION"


# ---------------------------------------------------------------------------
# Router (recommend-only, validated)
# ---------------------------------------------------------------------------
def test_router_forces_human_on_mandatory_reason():
    c = Classification(primary_intent="REFUND_REQUEST", requires_human=True,
                       human_reason="REFUND_REQUEST", conversation_route="MAIN_AGENT")
    d = select_route(c, ci("I want a refund."))
    assert d.route == "HUMAN_INTERVENTION"
    assert d.requires_human and d.validated_override


def test_router_downgrades_unvalidated_human():
    # model said HUMAN_INTERVENTION but did not set a mandatory reason
    c = Classification(primary_intent="COMPLAINT", requires_human=False,
                       conversation_route="HUMAN_INTERVENTION")
    d = select_route(c, ci("hmm"))
    assert d.route == "MAIN_AGENT"
    assert "downgraded_unvalidated_human" in d.notes


def test_router_clarification():
    c = Classification(primary_intent="REPAIR_REQUEST", needs_clarification=True,
                       conversation_route="NEEDS_CLARIFICATION")
    assert select_route(c, ci("I need a repair.")).route == "NEEDS_CLARIFICATION"


def test_router_template_candidate():
    c = Classification(primary_intent="PROCESS_ENQUIRY", conversation_route="DETERMINISTIC_HANDLER",
                       fixed_template_id="PROCESS_EXPLANATION")
    d = select_route(c, ci("How does the process work?"))
    assert d.route == "DETERMINISTIC_HANDLER" and d.fixed_template_id == "PROCESS_EXPLANATION"


# ---------------------------------------------------------------------------
# Lifecycle (backend-resolved)
# ---------------------------------------------------------------------------
def test_lifecycle_resolution():
    assert resolve_lifecycle(LifecycleFacts()) == "NEW_PROSPECT"
    assert resolve_lifecycle(LifecycleFacts(has_prior_conversation=True)) == "RETURNING_PROSPECT"
    assert resolve_lifecycle(LifecycleFacts(has_completed_order=True)) == "EXISTING_CUSTOMER"
    assert resolve_lifecycle(LifecycleFacts(has_active_order=True)) == "ACTIVE_CUSTOMER"
    assert resolve_lifecycle(LifecycleFacts(is_b2b_confirmed=True, has_active_order=True)) == "B2B_LEAD"


# ---------------------------------------------------------------------------
# Schema validation / repair
# ---------------------------------------------------------------------------
def test_schema_rejects_unknown_enum_values():
    raw = {
        "primary_intent": "NONSENSE_INTENT",
        "service_domain": "FLYING_CARPET",
        "sentiment": "EUPHORIC",
        "intent_confidence": 5.0,
        "frustration_level": 9,
        "secondary_intents": ["GREETING", "ALSO_NONSENSE"],
        "reason_codes": ["EXPLICIT_SERVICE_MENTION", "MADE_UP"],
    }
    c = Classification.from_tool_input(raw)
    assert c.primary_intent == "UNKNOWN"          # unknown → safe default
    assert c.service_domain == "UNKNOWN"
    assert c.sentiment == "NEUTRAL"
    assert c.intent_confidence == 1.0             # clamped to [0,1]
    assert c.frustration_level == 0               # out-of-range → 0
    assert c.secondary_intents == ["GREETING"]    # junk dropped
    assert c.reason_codes == ["EXPLICIT_SERVICE_MENTION"]


def test_schema_mandatory_reason_forces_requires_human():
    c = Classification.from_tool_input({"primary_intent": "REFUND_REQUEST",
                                        "human_reason": "REFUND_REQUEST",
                                        "requires_human": False})
    assert c.requires_human is True


def test_tool_schema_shape():
    s = CLASSIFIER_TOOL_SCHEMA["input_schema"]
    assert s["additionalProperties"] is False
    assert set(["primary_intent", "requires_human", "should_cancel_followups"]).issubset(set(s["required"]))
    assert s["properties"]["primary_intent"]["enum"] == list(tax.PRIMARY_INTENTS)


# ---------------------------------------------------------------------------
# Mandatory human-escalation recall = 100%
# ---------------------------------------------------------------------------
MANDATORY_CASES = [
    "I want a refund.",
    "You damaged my dress.",
    "One shirt is missing.",
    "I was charged twice.",
    "Clean it again for free.",
    "Let me speak to a manager.",
]


@pytest.mark.parametrize("text", MANDATORY_CASES)
async def test_mandatory_human_recall(text):
    c = await classify_turn(ci(text))
    assert c.requires_human is True, f"{text!r} did not escalate"
    assert c.human_reason in tax.MANDATORY_HUMAN_REASONS
    d = select_route(c, ci(text))
    assert d.route == "HUMAN_INTERVENTION"


# ---------------------------------------------------------------------------
# classify_turn orchestration (offline → rule engine)
# ---------------------------------------------------------------------------
async def test_classify_turn_offline_uses_rule_engine():
    c = await classify_turn(ci("I need wash and fold."))
    assert c.primary_intent == "SERVICE_SELECTION"
    assert c.status == ClassifierStatus.FALLBACK  # offline deterministic path


async def test_classify_turn_deterministic_shortcut():
    c = await classify_turn(ClassifierInput(message=MessageInput(text="", has_location=True)))
    assert c.primary_intent == "LOCATION_PIN_PROVIDED"
    assert c.status == ClassifierStatus.DETERMINISTIC


async def test_classify_turn_disabled_returns_unknown(monkeypatch):
    from settings import get_settings
    s = get_settings()
    monkeypatch.setattr(s, "whatsapp_classifier_enabled", False)
    c = await classify_turn(ci("I need wash and fold."), settings=s)
    assert c.primary_intent == "UNKNOWN"
    assert c.status == ClassifierStatus.FAILED


async def test_should_cancel_followups_on_normal_reply():
    c = await classify_turn(ci("I need wash and fold."))
    assert c.should_cancel_followups is True


async def test_low_confidence_downgrades_to_clarification():
    # a bare short reply with no context → low confidence → NEEDS_CLARIFICATION
    c = await classify_turn(ci("maybe"))
    assert c.needs_clarification or c.primary_intent in ("UNKNOWN", "GENERAL_ENQUIRY")
