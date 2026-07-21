"""Tests for the config-driven business & safety rule layer (RULE 1-11).

These assert that the agent's behaviour is actually driven by the
config/*.json rule files (welcome text, refusal, services, escalation,
mock-mode honesty) and covers the acceptance test cases from the rules spec:
greeting, book-pickup, track/cancel order, out-of-domain refusal, no invented
price, complaint escalation/handoff, mock-mode honesty, PII masking and
quick actions rendered inside agent messages.
"""
import pytest

from rules import (
    agent_rules,
    escalation_rules,
    quick_actions_config,
    refusal_message,
    service_catalog,
    welcome_message,
)
from services.escalation import detect_escalation
from services.privacy import mask_pii

MAIN_MENU_IDS = {a["id"] for a in quick_actions_config()["main_menu"]}
SERVICE_ACTION_IDS = {s["key"] for s in service_catalog()}


def _action_ids(body):
    return {a["id"] for a in body["actions"]}


# --- RULE 2: greeting -----------------------------------------------------

@pytest.mark.parametrize("text", ["Hi", "Hello", "hey there"])
async def test_greeting_returns_configured_welcome_and_menu(client, text):
    body = (await client.post("/api/test-chat/message", json={"message": text})).json()
    assert body["agent_reply"] == welcome_message()
    assert _action_ids(body) == MAIN_MENU_IDS
    # RULE 2 — actions are attached inside the message, all quick replies.
    assert body["actions"] and all(a["type"] == "quick_reply" for a in body["actions"])


# --- RULE 3: service options ---------------------------------------------

async def test_book_pickup_offers_only_configured_services(client):
    body = (
        await client.post(
            "/api/test-chat/message",
            json={"message": "Book Pickup", "action_id": "book_pickup"},
        )
    ).json()
    assert "which service" in body["agent_reply"].lower()
    assert _action_ids(body) == SERVICE_ACTION_IDS


# --- RULE 5: quick-action behaviour --------------------------------------

async def test_track_order_asks_for_order_id_in_demo_mode(client):
    body = (
        await client.post(
            "/api/test-chat/message",
            json={"message": "Track Order", "action_id": "track_order"},
        )
    ).json()
    reply = body["agent_reply"].lower()
    assert "order id" in reply
    assert "demo mode" in reply


async def test_cancel_order_asks_for_id_and_never_cancels(client):
    body = (
        await client.post(
            "/api/test-chat/message",
            json={"message": "Cancel Order", "action_id": "cancel_order"},
        )
    ).json()
    reply = body["agent_reply"].lower()
    assert "order id" in reply
    assert "still be cancelled" in reply
    for claim in ("cancelled successfully", "has been cancelled", "order cancelled"):
        assert claim not in reply


async def test_clicked_cancel_action_is_not_treated_as_escalation(client):
    """A structured button flow must keep its own safe copy, not the generic
    escalation handoff message."""
    body = (
        await client.post(
            "/api/test-chat/message",
            json={"message": "Cancel Order", "action_id": "cancel_order"},
        )
    ).json()
    assert body["agent_reply"] != escalation_rules()["handoff_message"]


# --- RULE 1: domain scope -------------------------------------------------

@pytest.mark.parametrize(
    "text", ["Can you write Python code?", "What is the capital of France?"]
)
async def test_out_of_domain_uses_configured_refusal(client, text):
    body = (await client.post("/api/test-chat/message", json={"message": text})).json()
    assert body["domain"] == "out_of_domain"
    assert body["agent_reply"] == refusal_message()
    assert body["provider"] == "none"  # RULE 1 — no LLM call out of domain
    assert _action_ids(body) == MAIN_MENU_IDS


# --- RULE 7: no invented data --------------------------------------------

async def test_unpriced_service_does_not_invent_a_price(client):
    body = (
        await client.post(
            "/api/test-chat/message", json={"message": "How much for curtains cleaning?"}
        )
    ).json()
    reply = body["agent_reply"].lower()
    assert "aed" not in reply  # no invented number
    assert "team will confirm" in reply


# --- RULE 6: escalation / handoff ----------------------------------------

@pytest.mark.parametrize(
    "text,expected_category",
    [
        ("I want to complain about my last order", "complaint"),
        ("I need a refund for my order", "refund"),
        ("You damaged my shirt", "damaged_item"),
        ("I was charged twice for my laundry order", "payment_issue"),
        ("I need a quotation for our hotel laundry", "b2b_quotation"),
    ],
)
async def test_high_risk_messages_escalate_to_human(client, text, expected_category):
    body = (await client.post("/api/test-chat/message", json={"message": text})).json()
    assert body["agent_reply"] == escalation_rules()["handoff_message"]
    assert body["provider"] == "none"  # handed off without an autonomous reply
    assert "call_support" in _action_ids(body)
    # the agent must not resolve it itself
    reply = body["agent_reply"].lower()
    for claim in ("refunded", "refund has been", "cancelled", "compensat"):
        assert claim not in reply
    assert detect_escalation(text) == expected_category


def test_detect_escalation_ignores_normal_booking_text():
    assert detect_escalation("I need a wash and fold pickup in Dubai Marina tomorrow") is None
    assert detect_escalation("How much for dry cleaning a suit?") is None


# --- RULE 4 / 9: mock-mode honesty ---------------------------------------

async def test_completed_booking_admits_demo_mode_and_claims_no_real_order(client):
    # Drive the booking flow to completion: service+area+time, then items,
    # then confirm. The confirmation reply must stay demo-honest.
    first = await client.post(
        "/api/test-chat/message",
        json={"message": "Wash & Fold\nDubai Marina\ntomorrow"},
    )
    conversation_id = first.json()["conversation_id"]
    await client.post(
        "/api/test-chat/message",
        json={"conversation_id": conversation_id, "message": "2 shirts and a pair of jeans"},
    )
    body = (
        await client.post(
            "/api/test-chat/message",
            json={
                "conversation_id": conversation_id,
                "message": "Confirm Booking",
                "action_id": "confirm_booking",
            },
        )
    ).json()
    reply = body["agent_reply"]
    assert "demo mode" in reply.lower()
    assert body["order_id"]  # a mock order was created behind the scenes
    assert body["order_status"] == "active"
    lowered = reply.lower()
    for claim in ("order placed", "successfully booked", "order confirmed"):
        assert claim not in lowered


# --- RULE 8: PII masking --------------------------------------------------

def test_mask_pii_masks_phone_and_email():
    assert "[phone hidden]" in mask_pii("Call me on +971 50 123 4567 please")
    assert "4567" not in mask_pii("Call me on +971 50 123 4567 please")
    assert mask_pii("reach me at nada@example.com") == "reach me at [email hidden]"


def test_mask_pii_preserves_order_ids_and_times():
    # Order IDs and short numbers are not phone-shaped and must survive intact.
    assert mask_pii("My order is LK-1023, pickup at 7pm") == "My order is LK-1023, pickup at 7pm"


def test_mask_pii_passes_through_plain_text():
    assert mask_pii("I need a wash and fold pickup") == "I need a wash and fold pickup"
    assert mask_pii(None) is None


# --- RULE 10: config wiring sanity ---------------------------------------

def test_service_buttons_match_service_catalog_config():
    from agents.whatsapp_agent.actions import SERVICE_ACTIONS

    assert {a.id for a in SERVICE_ACTIONS} == {s["key"] for s in service_catalog()}
    assert {a.label for a in SERVICE_ACTIONS} == {s["label"] for s in service_catalog()}


def test_welcome_and_refusal_come_from_config():
    assert welcome_message() == agent_rules()["welcome"]["message"]
    assert refusal_message() == agent_rules()["domain"]["refusal_message"]
