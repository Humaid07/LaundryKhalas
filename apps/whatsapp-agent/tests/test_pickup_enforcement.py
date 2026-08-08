"""Phase 4: pickup enforcement — address+pin first, backend slots, never an
open-ended pickup time (spec §10-15)."""
from agents.whatsapp_agent.booking_tools import booking_system_prompt
from services.customer_memory import next_location_ask, shape_saved_address


def test_ask_pin_when_address_present_pin_missing():
    shaped = shape_saved_address({"address": "Marina Tower, apt 5", "area": "Dubai Marina",
                                  "city": "Dubai"})
    assert shaped["pin_available"] is False
    assert next_location_ask(shaped) == "pin"


def test_ask_address_when_pin_present_address_missing():
    shaped = shape_saved_address({"latitude": 25.08, "longitude": 55.14})
    assert shaped["pin_available"] is True
    assert next_location_ask(shaped) == "address"


def test_none_when_both_present():
    shaped = shape_saved_address({"address": "Marina Tower, apt 5", "area": "Dubai Marina",
                                  "city": "Dubai", "latitude": 25.08, "longitude": 55.14})
    assert next_location_ask(shaped) is None


def test_ask_address_first_when_nothing_known():
    assert next_location_ask(shape_saved_address({})) == "address"
    assert next_location_ask(None) == "address"


def test_prompt_forbids_open_ended_pickup_time():
    p = booking_system_prompt().lower()
    # the no-open-ended-time rule is present and framed as a prohibition
    assert "never ask the customer what pickup time" in p
    assert "never ask an open-ended" in p


def test_prompt_requires_backend_slots():
    p = booking_system_prompt().lower()
    assert "present the actual available slots" in p
