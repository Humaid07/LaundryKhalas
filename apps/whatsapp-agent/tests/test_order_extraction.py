"""Tests for the WhatsApp order-capture extraction layer
(services/order_extraction.py). Pure functions — no DB required."""
from services.order_extraction import (
    OrderDetails,
    accumulate_from_messages,
    area_to_city,
    extract_address,
    extract_customer_order_details,
    extract_items,
    extract_name,
    extract_payment_method,
    is_confirmation,
)


# --- name -------------------------------------------------------------------
def test_extract_name_strong_trigger():
    assert extract_name("My name is Amaan and I am in Dubai Marina") == "Amaan"


def test_extract_name_ignores_location_after_i_am():
    # bare "I am in Dubai" must NOT be read as a name
    assert extract_name("I am in Dubai Marina") is None


def test_extract_name_call_me():
    assert extract_name("call me Sara please") == "Sara"


# --- area / city ------------------------------------------------------------
def test_area_maps_to_city():
    d = extract_customer_order_details("I am in Dubai Marina")
    assert d.area == "Dubai Marina"
    assert d.city == "Dubai"
    assert area_to_city("Dubai Marina") == "Dubai"


# --- address ----------------------------------------------------------------
def test_address_strips_leading_area():
    d = extract_customer_order_details(
        "My name is Amaan and pickup is Dubai Marina, Marina Gate, Tower 1"
    )
    assert d.name == "Amaan"
    assert d.area == "Dubai Marina"
    assert d.city == "Dubai"
    assert d.address == "Marina Gate, Tower 1"


def test_address_from_building_keywords():
    assert extract_address("Tower 3, Marina Gate, apartment 502") is not None


# --- items ------------------------------------------------------------------
def test_items_two_suits():
    items = extract_items("I need dry cleaning for two suits")
    assert {"item": "Suit", "quantity": 2} in items


def test_service_and_items_together():
    d = extract_customer_order_details("I need dry cleaning for two suits")
    assert d.service_key == "dry_cleaning"
    assert d.items == [{"item": "Suit", "quantity": 2}]


# --- payment ----------------------------------------------------------------
def test_payment_cash_on_delivery():
    assert extract_payment_method("Cash on delivery") == "Cash on delivery"
    assert extract_payment_method("I'll pay by card") == "Card"


# --- confirmation -----------------------------------------------------------
def test_confirmation():
    assert is_confirmation("Yes confirm") is True
    assert is_confirmation("not yet") is False


# --- accumulation across the whole conversation -----------------------------
def test_accumulate_full_booking_flow():
    d = accumulate_from_messages(
        [
            "Hi, I need laundry pickup today",
            "My name is Amaan and I am in Dubai Marina",
            "I need dry cleaning for two suits",
            "Pickup tomorrow evening",
            "Cash on delivery",
            "Yes confirm",
        ]
    )
    assert d.name == "Amaan"
    assert d.area == "Dubai Marina"
    assert d.city == "Dubai"
    assert d.service_key == "dry_cleaning"
    assert {"item": "Suit", "quantity": 2} in d.items
    assert d.pickup_slot in ("tomorrow", "evening")
    assert d.payment_method == "Cash on delivery"
    assert d.confirmed is True
    assert d.is_confirmable() is True


def test_confirmed_not_sticky_across_turns():
    # a 'yes' early, then a later non-confirming message -> confirmed resets
    d = accumulate_from_messages(["yes", "I need wash and fold in Deira"])
    assert d.confirmed is False


def test_has_booking_details_requires_a_slot():
    assert OrderDetails().has_booking_details() is False
    assert extract_customer_order_details("wash and fold please").has_booking_details() is True
