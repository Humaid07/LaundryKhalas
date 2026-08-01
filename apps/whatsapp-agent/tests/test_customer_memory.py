"""Durable returning-customer memory shaping — pure, offline (spec 2026-08-01)."""
from services.customer_memory import (
    build_returning_customer_context,
    shape_saved_address,
)

_CUST_A = {
    "id": "11111111-1111-1111-1111-111111111111",
    "masked_phone": "+9715•••••58",
    "phone_e164": "+971582003209",
    "customer_name": "Zoya",
    "customer_name_source": "CUSTOMER_CONFIRMED",
}
_CUST_B = {
    "id": "22222222-2222-2222-2222-222222222222",
    "masked_phone": "+9715•••••60",
    "phone_e164": "+971502485658",
    "customer_name": "Sam",
    "customer_name_source": "CUSTOMER_PROVIDED",
}
_ADDR = {
    "address_id": "aaaa1111-0000-0000-0000-000000000000",
    "typed_address": "Apartment 1204, Marina Heights, Dubai Marina",
    "building_name": "Marina Heights",
    "floor": "12",
    "apartment_number": "1204",
    "area": "Dubai Marina",
    "city": "Dubai",
    "emirate": "Dubai",
    "latitude": 25.08,
    "longitude": 55.14,
}


def test_returning_customer_with_confirmed_name():
    ctx = build_returning_customer_context(_CUST_A, persona="Sara")
    assert ctx["returning_customer"] is True
    assert ctx["customer_id"] == _CUST_A["id"]
    assert ctx["customer_name"] == "Zoya"
    assert ctx["customer_name_source"] in {"CUSTOMER_CONFIRMED", "CONFIRMED"}
    assert ctx["assigned_persona"] == "Sara"


def test_phone_number_is_masked_never_raw():
    ctx = build_returning_customer_context(_CUST_A)
    assert ctx["whatsapp_number"] == _CUST_A["masked_phone"]
    # the full E.164 number must never appear anywhere in the model-facing block
    assert _CUST_A["phone_e164"] not in str(ctx)


def test_empty_or_unidentified_customer_yields_empty_block():
    for bad in (None, {}, {"masked_phone": "x"}):  # no id → nothing usable
        assert build_returning_customer_context(bad) == {}


def test_saved_address_with_pin():
    ctx = build_returning_customer_context(_CUST_A, saved_address=_ADDR)
    sa = ctx["saved_address"]
    assert sa["typed_address"].startswith("Apartment 1204")
    assert sa["building"] == "Marina Heights"
    assert sa["unit"] == "1204"
    assert sa["pin_available"] is True
    assert sa["latitude"] == 25.08 and sa["longitude"] == 55.14


def test_saved_address_without_coords_has_no_pin():
    addr = {"typed_address": "Villa 7, JVC", "area": "JVC", "city": "Dubai"}
    sa = shape_saved_address(addr)
    assert sa["pin_available"] is False
    assert sa["latitude"] is None and sa["longitude"] is None


def test_unconfirmed_profile_name_is_not_used():
    cust = {"id": "33333333-3333-3333-3333-333333333333",
            "masked_phone": "+9715•••••00",
            "customer_name": "iPhone",
            "customer_name_source": "WHATSAPP_PROFILE"}
    ctx = build_returning_customer_context(cust)
    assert "customer_name" not in ctx  # untrusted profile name never greeted with


def test_explicit_confirmed_name_overrides():
    ctx = build_returning_customer_context(_CUST_A, confirmed_name="Zoya Khan")
    assert ctx["customer_name"] == "Zoya Khan"


def test_last_completed_order_id_included():
    ctx = build_returning_customer_context(_CUST_A, last_completed_order_id="order-xyz")
    assert ctx["last_completed_order_id"] == "order-xyz"


def test_memory_isolation_between_customers():
    a = build_returning_customer_context(_CUST_A, saved_address=_ADDR)
    b = build_returning_customer_context(_CUST_B)
    # B's block must contain none of A's identity or address
    assert b["customer_id"] != a["customer_id"]
    assert "Zoya" not in str(b)
    assert "Marina Heights" not in str(b)
    assert "saved_address" not in b  # B had no saved address passed in
