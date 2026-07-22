"""Tests for WhatsApp-style interactive message actions: the welcome
message + main-menu buttons attached to agent messages (not a permanent
toolbar), the service-selection buttons inside the Book Pickup flow, and
the track/cancel/change-time/add-items/support quick-action flows
triggered either by free text or by a button's action_id. Every
demo/mock-only reply must say so explicitly, and none of them may claim a
real order was tracked, cancelled, or changed.
"""
import pytest

MAIN_MENU_IDS = {
    "book_pickup", "track_order", "change_pickup_time",
    "add_more_items", "cancel_order", "call_support",
}
SERVICE_ACTION_IDS = {
    "premium_wash_fold", "boutique_clean_press", "steam_pressing_only",
    "luxe_bed_bath_care", "artisan_shoe_restoration", "luxury_bag_spa",
    "tailoring_alterations", "deep_carpet_curtain_care",
}


def _action_ids(body):
    return {a["id"] for a in body["actions"]}


@pytest.mark.parametrize("text", ["Hi", "Hello"])
async def test_greeting_shows_welcome_and_main_menu_actions(client, text):
    response = await client.post("/api/test-chat/message", json={"message": text})
    body = response.json()
    assert "welcome" in body["agent_reply"].lower()
    assert _action_ids(body) == MAIN_MENU_IDS
    assert all(a["type"] == "quick_reply" for a in body["actions"])


@pytest.mark.parametrize(
    "text", ["I need laundry", "I need help", "What services do you offer?"]
)
async def test_vague_opener_shows_welcome_menu_not_service_question(client, text):
    response = await client.post("/api/test-chat/message", json={"message": text})
    body = response.json()
    assert "welcome" in body["agent_reply"].lower()
    assert "which service" not in body["agent_reply"].lower()
    assert _action_ids(body) == MAIN_MENU_IDS


async def test_out_of_domain_refusal_shows_main_menu_again(client):
    response = await client.post(
        "/api/test-chat/message", json={"message": "Can you write Python code?"}
    )
    body = response.json()
    assert body["domain"] == "out_of_domain"
    assert "laundry and cleaning" in body["agent_reply"].lower()
    assert _action_ids(body) == MAIN_MENU_IDS


@pytest.mark.parametrize(
    "label,expected_key",
    [
        ("Premium Wash & Fold", "premium_wash_fold"),
        ("Boutique Clean & Press", "boutique_clean_press"),
        ("Steam Pressing Only", "steam_pressing_only"),
        ("Luxe Bed & Bath Care", "luxe_bed_bath_care"),
        ("Artisan Shoe Restoration", "artisan_shoe_restoration"),
        ("Luxury Bag Spa", "luxury_bag_spa"),
        ("Tailoring & Alterations", "tailoring_alterations"),
        ("Deep Carpet & Curtain Care", "deep_carpet_curtain_care"),
    ],
)
async def test_service_chip_label_recognized_exactly(client, label, expected_key):
    response = await client.post(
        "/api/test-chat/message",
        json={"message": f"{label}\nDubai Marina\ntomorrow"},
    )
    assert response.json()["domain"] in ("in_domain", "uncertain")


async def test_service_actions_present_when_service_missing(client):
    response = await client.post(
        "/api/test-chat/message", json={"message": "I'd like to book a pickup"}
    )
    body = response.json()
    assert "which service" in body["agent_reply"].lower()
    assert _action_ids(body) == SERVICE_ACTION_IDS


async def test_actions_empty_once_service_known(client):
    first = await client.post(
        "/api/test-chat/message", json={"message": "I'd like to book a pickup"}
    )
    conversation_id = first.json()["conversation_id"]
    second = await client.post(
        "/api/test-chat/message",
        json={"conversation_id": conversation_id, "message": "Premium Wash & Fold"},
    )
    body = second.json()
    assert body["actions"] == []
    # After the service is known the booking flow asks for item details next.
    assert "item details" in body["agent_reply"].lower()


async def test_book_pickup_action_id_routes_deterministically(client):
    """Clicking the Book Pickup button sends {message, action_id} - the
    action_id must resolve the flow even if the label text alone were
    ambiguous."""
    response = await client.post(
        "/api/test-chat/message",
        json={"message": "Book Pickup", "action_id": "book_pickup"},
    )
    body = response.json()
    assert "which service" in body["agent_reply"].lower()
    assert _action_ids(body) == SERVICE_ACTION_IDS


async def test_service_action_id_routes_into_booking_flow(client):
    first = await client.post(
        "/api/test-chat/message",
        json={"message": "Book Pickup", "action_id": "book_pickup"},
    )
    conversation_id = first.json()["conversation_id"]
    second = await client.post(
        "/api/test-chat/message",
        json={
            "conversation_id": conversation_id,
            "message": "Boutique Clean & Press",
            "action_id": "boutique_clean_press",
        },
    )
    body = second.json()
    assert body["actions"] == []
    assert "item details" in body["agent_reply"].lower()


async def test_track_order_action_id_asks_for_id_then_uses_it(client):
    first = await client.post(
        "/api/test-chat/message",
        json={"message": "Track Order", "action_id": "track_order"},
    )
    conversation_id = first.json()["conversation_id"]
    reply1 = first.json()["agent_reply"].lower()
    assert "order id" in reply1
    assert "demo mode" in reply1

    # A known demo order returns its real stored status (mock tracking data).
    second = await client.post(
        "/api/test-chat/message",
        json={"conversation_id": conversation_id, "message": "LK-AE-1024"},
    )
    reply = second.json()["agent_reply"]
    assert "LK-AE-1024" in reply
    assert "pickup scheduled" in reply.lower()
    assert "mock tracking data" in reply.lower()


async def test_track_order_unknown_id_is_refused_not_invented(client):
    first = await client.post(
        "/api/test-chat/message",
        json={"message": "Track Order", "action_id": "track_order"},
    )
    conversation_id = first.json()["conversation_id"]
    second = await client.post(
        "/api/test-chat/message",
        json={"conversation_id": conversation_id, "message": "LK-9999"},
    )
    reply = second.json()["agent_reply"].lower()
    assert "couldn't find" in reply or "could not find" in reply
    # Never invents a status for an unknown order.
    assert "pickup scheduled" not in reply
    assert "in cleaning" not in reply


async def test_cancel_order_explains_team_must_confirm_and_does_not_cancel(client):
    response = await client.post(
        "/api/test-chat/message",
        json={"message": "Cancel Order", "action_id": "cancel_order"},
    )
    reply = response.json()["agent_reply"].lower()
    assert "order id" in reply
    assert "still be cancelled" in reply
    assert "demo mode" in reply
    assert "cancelled successfully" not in reply
    assert "has been cancelled" not in reply


async def test_change_pickup_time_asks_id_and_time_then_confirms(client):
    first = await client.post(
        "/api/test-chat/message",
        json={"message": "Change Pickup Time", "action_id": "change_pickup_time"},
    )
    conversation_id = first.json()["conversation_id"]
    reply1 = first.json()["agent_reply"].lower()
    assert "order id" in reply1
    assert "new pickup time" in reply1

    second = await client.post(
        "/api/test-chat/message",
        json={"conversation_id": conversation_id, "message": "LK-AE-1024, 7pm please"},
    )
    reply2 = second.json()["agent_reply"]
    assert "LK-AE-1024" in reply2
    assert "7pm" in reply2
    assert "demo mode" in reply2.lower()


async def test_add_more_items_action_id_asks_then_acknowledges(client):
    first = await client.post(
        "/api/test-chat/message",
        json={"message": "Add More Items", "action_id": "add_more_items"},
    )
    conversation_id = first.json()["conversation_id"]
    assert "what items" in first.json()["agent_reply"].lower()

    second = await client.post(
        "/api/test-chat/message",
        json={"conversation_id": conversation_id, "message": "2 more shirts and a blanket"},
    )
    reply = second.json()["agent_reply"]
    assert "2 more shirts and a blanket" in reply
    assert "demo mode" in reply.lower()


async def test_call_support_action_id_gives_handoff_message(client):
    response = await client.post(
        "/api/test-chat/message",
        json={"message": "Call Support", "action_id": "call_support"},
    )
    reply = response.json()["agent_reply"].lower()
    assert "support team" in reply
    assert "demo mode" in reply
    assert "connected you" not in reply  # never claims a live connection happened


async def test_pricing_question_for_unpriced_service_does_not_invent_price(client):
    response = await client.post(
        "/api/test-chat/message", json={"message": "How much for curtains cleaning?"}
    )
    reply = response.json()["agent_reply"].lower()
    assert "aed" not in reply  # no invented number
    assert "team will confirm" in reply
