"""Wire hesitation + next_location_ask into the live turn: deterministic per-turn
signals injected into the booking state block (spec §11/§17)."""
from agents.whatsapp_agent.booking_tools import booking_system_prompt, conversation_signals


def test_price_objection_signal():
    assert conversation_signals("that's too expensive", None)["customer_signal"] == "PRICE_OBJECTION"


def test_price_enquiry_signal():
    assert conversation_signals("how much for 5 shirts?", None)["customer_signal"] == "PRICE_ENQUIRY"


def test_no_signal_for_neutral_message():
    assert "customer_signal" not in conversation_signals("I want a pickup from Marina", None)


def test_pickup_needs_pin_when_address_present():
    row = {"pickup_address": "Marina Tower apt 5", "pickup_area": "Dubai Marina"}
    assert conversation_signals("ok", row)["pickup_location_needed"] == "pin"


def test_pickup_needs_address_when_pin_present():
    row = {"pickup_latitude": 25.08, "pickup_longitude": 55.14}
    assert conversation_signals("ok", row)["pickup_location_needed"] == "address"


def test_pickup_none_when_both_present():
    row = {"pickup_address": "Marina Tower apt 5", "pickup_latitude": 25.08, "pickup_longitude": 55.14}
    assert conversation_signals("ok", row)["pickup_location_needed"] is None


def test_no_pickup_field_without_active_order():
    assert "pickup_location_needed" not in conversation_signals("hi", None)


def test_prompt_explains_the_state_signals():
    p = booking_system_prompt().lower()
    assert "customer_signal" in p
    assert "pickup_location_needed" in p
