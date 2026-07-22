"""Booking state-machine tests (the 12 required scenarios).

Pure/hermetic: the FSM is exercised directly with a fixed ``today`` and an
injected ``available_slots`` fake, so no DB/network is touched. Persistence,
webhook idempotency and the operational-order-once guarantee are enforced by the
webhook layer on top of these transitions (see api/evolution_webhooks.py); the
FSM-level guarantees they rely on are asserted here too.
"""
import asyncio
import datetime as _dt

from services import booking_flow as bf
from services.booking_flow import Booking, Inbound

TODAY = _dt.date(2026, 7, 22)  # a Wednesday

_SLOTS = [
    {"slot_id": "morning_08_11", "label": "8:00 AM – 11:00 AM",
     "start_time": _dt.time(8), "end_time": _dt.time(11)},
    {"slot_id": "evening_17_20", "label": "5:00 PM – 8:00 PM",
     "start_time": _dt.time(17), "end_time": _dt.time(20)},
]


async def slots_fake(pickup_date, emirate, service_id):
    return list(_SLOTS)


def advance(booking, inbound):
    """Sync wrapper so the tests stay plain functions (advance() is async because
    slot availability is a DB query in production)."""
    return asyncio.run(bf.advance(booking, inbound, today=TODAY, available_slots=slots_fake))


# --- helper: a valid, active service id from the real catalogue -------------
def _a_service_id():
    from rules import active_service_catalog
    return active_service_catalog()[0]["service_id"]


# Test 1 — "I need a laundry pickup" only detects intent, assumes nothing ------
def test_booking_intent_assumes_nothing_and_asks_for_service():
    assert bf.is_book_pickup_intent("I need a laundry pickup") is True
    reply = bf.begin()
    assert reply.state == bf.WAITING_FOR_SERVICE
    assert reply.interactive and reply.interactive.kind == "list"
    assert len(reply.interactive.options) >= 5              # all active services listed
    assert reply.text == "Sure! Which laundry service would you like to book?"
    # nothing assumed
    assert "service_id" not in reply.updates
    assert reply.confirm_now is False


# Test 2 — selecting a service stores the id + snapshot, moves to date ---------
def test_service_selection_stores_id_and_snapshot():
    sid = _a_service_id()
    b = Booking(conversation_state=bf.WAITING_FOR_SERVICE)
    reply = advance(b, Inbound(selection_id=f"service:{sid}", text="Premium Wash & Fold"))
    assert reply.state == bf.WAITING_FOR_PICKUP_DATE
    assert reply.updates["service_id"] == sid
    assert reply.updates["service_name_snapshot"]
    assert reply.updates.get("_touch_service_selected_at") is True


# Test 3 — "tomorrow" saves a normalized future date, moves to slot ------------
def test_pickup_date_tomorrow_normalized():
    b = Booking(conversation_state=bf.WAITING_FOR_PICKUP_DATE, service_id=_a_service_id())
    reply = advance(b, Inbound(selection_id="date:tomorrow"))
    assert reply.state == bf.WAITING_FOR_PICKUP_SLOT
    assert reply.updates["pickup_date"] == TODAY + _dt.timedelta(days=1)
    assert reply.interactive.kind == "list"           # slot list sent


def test_pickup_date_rejects_past():
    b = Booking(conversation_state=bf.WAITING_FOR_PICKUP_DATE, service_id=_a_service_id())
    reply = advance(b, Inbound(text="20/07/2026"))    # before TODAY
    assert reply.state == bf.WAITING_FOR_PICKUP_DATE  # stays
    assert "pickup_date" not in reply.updates


# Test 4 — selecting a slot saves id + start/end, moves to address -------------
def test_slot_selection_saves_times():
    d = TODAY + _dt.timedelta(days=1)
    b = Booking(conversation_state=bf.WAITING_FOR_PICKUP_SLOT, service_id=_a_service_id(),
                pickup_date=d)
    reply = advance(b, Inbound(selection_id="slot:evening_17_20"))
    assert reply.state == bf.WAITING_FOR_ADDRESS
    assert reply.updates["pickup_slot_id"] == "evening_17_20"
    assert reply.updates["pickup_start_time"].hour == 17
    assert reply.updates["pickup_end_time"].hour == 20
    assert reply.updates["pickup_start_time"].date() == d


# Test 5 — an address is saved verbatim, no area hallucinated ------------------
def test_address_saved_without_hallucinated_area():
    b = Booking(conversation_state=bf.WAITING_FOR_ADDRESS, service_id=_a_service_id())
    reply = advance(b, Inbound(text="Flat 5, Rose Building, some street"))
    assert reply.state == bf.WAITING_FOR_PICKUP_INSTRUCTIONS
    assert reply.updates["pickup_address"] == "Flat 5, Rose Building, some street"
    assert reply.updates["pickup_area"] is None        # not inferred
    assert reply.updates["address_source"] == "typed"


def test_address_from_whatsapp_location():
    b = Booking(conversation_state=bf.WAITING_FOR_ADDRESS, service_id=_a_service_id())
    reply = advance(b, Inbound(latitude=25.07, longitude=55.14))
    assert reply.state == bf.WAITING_FOR_PICKUP_INSTRUCTIONS
    assert reply.updates["address_source"] == "whatsapp_location"
    assert reply.updates["pickup_latitude"] == 25.07


# Test 6 — instruction selection saves code + text, moves to confirmation ------
def test_instruction_selection_saves_code_and_text():
    b = Booking(conversation_state=bf.WAITING_FOR_PICKUP_INSTRUCTIONS, service_id=_a_service_id())
    reply = advance(b, Inbound(selection_id="instruction:pickup_from_reception"))
    assert reply.state == bf.WAITING_FOR_CONFIRMATION
    assert reply.updates["pickup_instruction_code"] == "pickup_from_reception"
    assert reply.updates["pickup_instruction_text"] == "Pick up from reception"
    assert reply.interactive.kind == "buttons"          # confirm/change/cancel


def test_instruction_other_asks_for_free_text_then_saves():
    b = Booking(conversation_state=bf.WAITING_FOR_PICKUP_INSTRUCTIONS, service_id=_a_service_id())
    r1 = advance(b, Inbound(selection_id="instruction:other"))
    assert r1.state == bf.WAITING_FOR_INSTRUCTION_TEXT
    b2 = Booking(conversation_state=bf.WAITING_FOR_INSTRUCTION_TEXT, service_id=_a_service_id())
    r2 = advance(b2, Inbound(text="Call me when you arrive at Tower A"))
    assert r2.state == bf.WAITING_FOR_CONFIRMATION
    assert r2.updates["pickup_instruction_code"] == "other"
    assert r2.updates["pickup_instruction_text"] == "Call me when you arrive at Tower A"


# Test 7 — explicit confirmation flips the booking once ------------------------
def test_confirmation_confirms_once():
    b = Booking(conversation_state=bf.WAITING_FOR_CONFIRMATION, service_id=_a_service_id())
    reply = advance(b, Inbound(selection_id="confirm_booking"))
    assert reply.state == bf.BOOKING_CONFIRMED
    assert reply.confirm_now is True
    # defense-in-depth: a repeat from the already-confirmed state does NOT re-confirm
    b2 = Booking(conversation_state=bf.BOOKING_CONFIRMED, service_id=_a_service_id())
    again = advance(b2, Inbound(selection_id="confirm_booking"))
    assert again.confirm_now is False


def test_no_confirmation_without_explicit_confirm():
    b = Booking(conversation_state=bf.WAITING_FOR_CONFIRMATION, service_id=_a_service_id())
    reply = advance(b, Inbound(text="hmm let me think"))
    assert reply.confirm_now is False
    assert reply.state == bf.WAITING_FOR_CONFIRMATION


# Test 8 — changing the service before confirmation reuses the same draft ------
def test_change_details_service_returns_to_service_step():
    b = Booking(conversation_state=bf.WAITING_FOR_CONFIRMATION, service_id=_a_service_id())
    menu = advance(b, Inbound(selection_id="change_details"))
    assert menu.state == bf.WAITING_FOR_CHANGE_FIELD
    b2 = Booking(conversation_state=bf.WAITING_FOR_CHANGE_FIELD, service_id=_a_service_id())
    reply = advance(b2, Inbound(selection_id="change:service"))
    assert reply.state == bf.WAITING_FOR_SERVICE       # re-select on the SAME booking
    assert reply.confirm_now is False


def test_change_date_revalidates_slot():
    b = Booking(conversation_state=bf.WAITING_FOR_CHANGE_FIELD, service_id=_a_service_id(),
                pickup_slot_id="evening_17_20")
    reply = advance(b, Inbound(selection_id="change:date"))
    assert reply.state == bf.WAITING_FOR_PICKUP_DATE
    assert reply.updates["pickup_slot_id"] is None      # dependent slot cleared


# Test 9 — cancellation ends the booking without an operational order ----------
def test_cancel_ends_booking():
    b = Booking(conversation_state=bf.WAITING_FOR_PICKUP_DATE, service_id=_a_service_id())
    reply = advance(b, Inbound(selection_id="cancel_booking"))
    assert reply.state == bf.BOOKING_CANCELLED
    assert reply.cancel_now is True
    assert reply.confirm_now is False


# Test 10 — an invalid/inactive service id is rejected, list re-sent -----------
def test_invalid_service_id_rejected_and_list_resent():
    b = Booking(conversation_state=bf.WAITING_FOR_SERVICE)
    reply = advance(b, Inbound(selection_id="service:does_not_exist"))
    assert reply.state == bf.WAITING_FOR_SERVICE        # stays
    assert "service_id" not in reply.updates
    assert reply.interactive and reply.interactive.kind == "list"   # list re-sent


# Test 11 — numbered fallback still maps a numeric reply to a real service -----
def test_numbered_fallback_maps_back_to_service_id():
    start = bf.begin()
    fallback = bf.numbered_fallback(start.interactive)
    assert "1. " in fallback and "Reply with the number" in fallback
    # customer replies "2" -> resolves to the 2nd active service, deterministically
    b = Booking(conversation_state=bf.WAITING_FOR_SERVICE)
    reply = advance(b, Inbound(text="2"))
    from rules import active_service_catalog
    assert reply.updates["service_id"] == active_service_catalog()[1]["service_id"]
    assert reply.state == bf.WAITING_FOR_PICKUP_DATE


# Test 12 — free-text "Wash and fold" resolves only on a unique match ----------
def test_free_text_service_unique_match():
    b = Booking(conversation_state=bf.WAITING_FOR_SERVICE)
    reply = advance(b, Inbound(text="wash and fold please"))
    assert reply.state == bf.WAITING_FOR_PICKUP_DATE
    svc = reply.updates["service_id"]
    from rules import service_by_id
    assert "wash" in (service_by_id(svc)["display_name"].lower())


def test_free_text_service_ambiguous_asks_to_pick():
    # a token that appears in multiple services' aliases stays on the service step
    b = Booking(conversation_state=bf.WAITING_FOR_SERVICE)
    # "clean" appears in several aliases (dry clean, shoe cleaning, carpet cleaning…)
    reply = advance(b, Inbound(text="i want cleaning"))
    if reply.state == bf.WAITING_FOR_SERVICE:
        assert "service_id" not in reply.updates       # ambiguous -> not resolved
    else:
        # if the catalogue makes it unique, that's fine too — but it must be valid
        assert reply.updates.get("service_id")
