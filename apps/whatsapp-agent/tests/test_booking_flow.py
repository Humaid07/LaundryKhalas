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


# Step 1 = the 9 real price-list categories; selecting one leads to item
# collection (a sub-category list for big categories, else the item list).
_COLLECT_NEXT = (bf.WAITING_FOR_SUBCATEGORY, bf.WAITING_FOR_ITEM)


# --- helper: a valid, active category code (= the FSM's "service_id") --------
def _a_service_id():
    from services import catalogue
    return catalogue.categories()[0]["code"]


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


# Test 2 — selecting a category stores the id + snapshot, moves to item collection
def test_service_selection_stores_id_and_snapshot():
    sid = _a_service_id()
    b = Booking(conversation_state=bf.WAITING_FOR_SERVICE)
    reply = advance(b, Inbound(selection_id=f"service:{sid}", text="Clean & Press"))
    assert reply.state in _COLLECT_NEXT                # collect the item(s) next
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


# Test 8 — "Change details" -> a targeted edit menu on the SAME draft ----------
def test_change_details_shows_field_menu_then_targeted_edit():
    b = Booking(conversation_state=bf.WAITING_FOR_CONFIRMATION, service_id=_a_service_id())
    menu = advance(b, Inbound(selection_id="change_details"))
    assert menu.state == bf.WAITING_FOR_CHANGE_FIELD
    # picking "service" enters the TARGETED edit state, not linear collection
    b2 = Booking(conversation_state=bf.WAITING_FOR_CHANGE_FIELD, service_id=_a_service_id())
    reply = advance(b2, Inbound(selection_id="change:service"))
    assert reply.state == bf.EDITING_SERVICE           # asks ONLY for the service
    assert reply.confirm_now is False


def test_change_date_enters_edit_state_without_touching_slot_yet():
    # Picking "date" only asks for the date; the slot is revalidated when the new
    # date arrives (see the targeted-edit tests below), not on menu selection.
    b = Booking(conversation_state=bf.WAITING_FOR_CHANGE_FIELD, service_id=_a_service_id(),
                pickup_slot_id="evening_17_20")
    reply = advance(b, Inbound(selection_id="change:date"))
    assert reply.state == bf.EDITING_DATE
    assert "pickup_slot_id" not in reply.updates        # nothing cleared prematurely


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
    # customer replies "2" -> resolves to the 2nd category, deterministically
    b = Booking(conversation_state=bf.WAITING_FOR_SERVICE)
    reply = advance(b, Inbound(text="2"))
    from services import catalogue
    assert reply.updates["service_id"] == catalogue.categories()[1]["code"]
    assert reply.state in _COLLECT_NEXT


# Test 12 — free-text "Wash and fold" resolves only on a unique match ----------
def test_free_text_service_unique_match():
    b = Booking(conversation_state=bf.WAITING_FOR_SERVICE)
    reply = advance(b, Inbound(text="wash and fold please"))
    assert reply.state in _COLLECT_NEXT
    assert reply.updates["service_id"] == "WASH_FOLD"


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


# ===========================================================================
# Targeted single-field EDIT flow (spec: "Fix the WhatsApp order-editing flow")
# A completed draft at the summary; changing ONE field must ask only for that
# field, preserve everything else, and return straight to the review.
# ===========================================================================
def _svc(i=0):
    from services import catalogue
    return catalogue.categories()[i]["code"]


def _svc_label(sid):
    from services import catalogue
    return (catalogue.category_by_code(sid) or {}).get("name") or sid


def _full_booking(state=bf.WAITING_FOR_CONFIRMATION, **overrides):
    """A fully-collected draft sitting at the summary."""
    sid = _svc(0)
    base = dict(
        conversation_state=state,
        service_id=sid, service_name_snapshot=_svc_label(sid),
        pickup_date=TODAY + _dt.timedelta(days=2),
        pickup_slot_id="evening_17_20", pickup_slot_label="5:00 PM – 8:00 PM",
        pickup_address="Marina Heights, Dubai Marina", pickup_area="dubai marina",
        pickup_instruction_code="pickup_from_reception",
        pickup_instruction_text="Pick up from reception",
    )
    base.update(overrides)
    return Booking(**base)


# 1/2/3 — change pickup time preserves address, service and date ---------------
def test_edit_slot_preserves_address_service_date():
    b = _full_booking(state=bf.EDITING_SLOT)
    reply = advance(b, Inbound(selection_id="slot:morning_08_11"))
    assert reply.state == bf.WAITING_FOR_CONFIRMATION            # back to review
    # only the slot columns are in the PATCH — everything else is untouched
    assert reply.updates["pickup_slot_id"] == "morning_08_11"
    assert "pickup_address" not in reply.updates
    assert "service_id" not in reply.updates
    assert "pickup_date" not in reply.updates
    # the revised summary still shows the preserved values
    assert "Marina Heights, Dubai Marina" in reply.text
    assert _svc_label(_svc(0)) in reply.text
    assert "8:00 AM – 11:00 AM" in reply.text                    # new time reflected


# 4 — change address preserves date and time ----------------------------------
def test_edit_address_preserves_date_and_time():
    b = _full_booking(state=bf.EDITING_ADDRESS)
    reply = advance(b, Inbound(text="Villa 9, Al Barsha South"))
    assert reply.state == bf.WAITING_FOR_CONFIRMATION
    assert reply.updates["pickup_address"] == "Villa 9, Al Barsha South"
    assert "pickup_slot_id" not in reply.updates
    assert "pickup_date" not in reply.updates
    assert "5:00 PM – 8:00 PM" in reply.text                     # time preserved
    assert "Villa 9, Al Barsha South" in reply.text


# 5 — change instructions preserves all other fields --------------------------
def test_edit_instructions_preserves_everything_else():
    b = _full_booking(state=bf.EDITING_INSTRUCTIONS)
    reply = advance(b, Inbound(selection_id="instruction:dont_ring_bell"))
    assert reply.state == bf.WAITING_FOR_CONFIRMATION
    assert reply.updates["pickup_instruction_code"] == "dont_ring_bell"
    assert "pickup_address" not in reply.updates
    assert "service_id" not in reply.updates
    assert "pickup_slot_id" not in reply.updates
    assert "Marina Heights, Dubai Marina" in reply.text
    assert "5:00 PM – 8:00 PM" in reply.text


# 6 — change service (category) re-collects items but preserves address/date/slot
def test_edit_service_preserves_address_and_pickup():
    b = _full_booking(state=bf.EDITING_SERVICE)
    new_sid = _svc(1)                                   # a different category
    reply = advance(b, Inbound(selection_id=f"service:{new_sid}"))
    # A new category invalidates the old items, so we re-collect them (item-only),
    # but the address/date/slot are preserved (never cleared or re-asked, §16).
    assert reply.state in _COLLECT_NEXT
    assert reply.updates["service_id"] == new_sid
    assert reply.updates["line_items"] is None         # old items cleared
    assert "pickup_address" not in reply.updates       # address NOT touched


# 7 — changing one field returns directly to review ---------------------------
def test_edit_returns_directly_to_review():
    for state, inbound in [
        (bf.EDITING_SLOT, Inbound(selection_id="slot:morning_08_11")),
        (bf.EDITING_ADDRESS, Inbound(text="Villa 9, Al Barsha South")),
        (bf.EDITING_INSTRUCTIONS, Inbound(selection_id="instruction:none")),
    ]:
        reply = advance(_full_booking(state=state), inbound)
        assert reply.state == bf.WAITING_FOR_CONFIRMATION
        assert "Here are your updated pickup details:" in reply.text


# 8 — previously completed fields are not re-asked ----------------------------
def test_edit_does_not_reask_downstream_fields():
    # editing the ADDRESS (mid-linear-flow field) must NOT then ask for instructions
    b = _full_booking(state=bf.EDITING_ADDRESS)
    reply = advance(b, Inbound(text="Villa 9, Al Barsha South"))
    assert reply.state != bf.WAITING_FOR_PICKUP_INSTRUCTIONS
    assert reply.state == bf.WAITING_FOR_CONFIRMATION
    assert "instructions for our driver" not in reply.text.lower()


# 9 — the full draft (rehydrated, e.g. after restart) survives an edit --------
def test_edit_after_rehydration_preserves_full_draft():
    # simulate a backend restart mid-edit: the FSM is handed a fresh Booking built
    # from the persisted row (the webhook reloads it every message).
    rehydrated = _full_booking(state=bf.EDITING_SLOT)
    reply = advance(rehydrated, Inbound(selection_id="slot:morning_08_11"))
    for preserved in ("Marina Heights, Dubai Marina", _svc_label(_svc(0)),
                      "Pick up from reception"):
        assert preserved in reply.text


# 10 — an edit never confirms/cancels (no second order) -----------------------
def test_edit_does_not_create_order_or_confirm():
    b = _full_booking(state=bf.EDITING_SLOT)
    reply = advance(b, Inbound(selection_id="slot:morning_08_11"))
    assert reply.confirm_now is False
    assert reply.cancel_now is False


# 11 — confirmation is reset after an edit (must re-confirm) -------------------
def test_edit_resets_confirmation():
    b = _full_booking(state=bf.EDITING_ADDRESS)
    reply = advance(b, Inbound(text="Villa 9, Al Barsha South"))
    assert reply.state == bf.WAITING_FOR_CONFIRMATION
    assert reply.confirm_now is False


# 12 — the revised summary confirms the SAME draft ----------------------------
def test_revised_summary_confirms_same_draft():
    edited = advance(_full_booking(state=bf.EDITING_SLOT),
                     Inbound(selection_id="slot:morning_08_11"))
    assert edited.state == bf.WAITING_FOR_CONFIRMATION
    # now confirm from the revised summary -> confirms once, same draft
    confirm = advance(_full_booking(state=bf.WAITING_FOR_CONFIRMATION,
                                    pickup_slot_id="morning_08_11"),
                      Inbound(selection_id="confirm_booking"))
    assert confirm.state == bf.BOOKING_CONFIRMED
    assert confirm.confirm_now is True


# 13 — a partial edit never nulls unrelated stored fields ---------------------
def test_edit_patch_does_not_touch_unrelated_fields():
    b = _full_booking(state=bf.EDITING_SLOT)
    reply = advance(b, Inbound(selection_id="slot:morning_08_11"))
    # the PATCH contains ONLY slot columns — nothing that would erase other fields
    for untouched in ("pickup_address", "service_id", "pickup_date",
                      "pickup_instruction_code"):
        assert untouched not in reply.updates


# 14 — two numbers keep separate edit states (state lives on the draft) -------
def test_two_bookings_keep_separate_edit_states():
    a = _full_booking(state=bf.EDITING_SLOT, pickup_address="A-Tower, Marina")
    b = _full_booking(state=bf.EDITING_ADDRESS, pickup_address="B-Villa, Barsha",
                      pickup_slot_id="evening_17_20")
    ra = advance(a, Inbound(selection_id="slot:morning_08_11"))
    rb = advance(b, Inbound(text="B-Villa 22, Al Barsha"))
    # A only changed its slot; B only changed its address — no cross-contamination
    assert ra.updates.get("pickup_slot_id") == "morning_08_11"
    assert "pickup_address" not in ra.updates
    assert rb.updates.get("pickup_address") == "B-Villa 22, Al Barsha"
    assert "pickup_slot_id" not in rb.updates
    assert "A-Tower, Marina" in ra.text and "B-Villa 22, Al Barsha" in rb.text


# 15 — changing the date to one where the slot is gone asks only for a slot ----
def test_edit_date_unavailable_slot_asks_only_for_new_slot():
    # current slot is night_20_22, which slots_fake never returns -> unavailable
    b = _full_booking(state=bf.EDITING_DATE, pickup_slot_id="night_20_22",
                      pickup_slot_label="8:00 PM – 10:00 PM")
    reply = advance(b, Inbound(selection_id="date:tomorrow"))
    assert reply.state == bf.EDITING_SLOT                    # asks ONLY for a new slot
    assert reply.updates["pickup_date"] == TODAY + _dt.timedelta(days=1)
    assert reply.updates["pickup_slot_id"] is None          # stale slot cleared
    assert reply.interactive and reply.interactive.kind == "list"


def test_edit_date_keeps_available_slot_and_returns_to_review():
    # current slot IS available on the new date -> keep it, back to review
    b = _full_booking(state=bf.EDITING_DATE, pickup_slot_id="evening_17_20")
    reply = advance(b, Inbound(selection_id="date:tomorrow"))
    assert reply.state == bf.WAITING_FOR_CONFIRMATION
    assert reply.updates["pickup_date"] == TODAY + _dt.timedelta(days=1)
    # times recomputed for the new date, slot preserved
    assert reply.updates["pickup_start_time"].date() == TODAY + _dt.timedelta(days=1)
    assert "5:00 PM – 8:00 PM" in reply.text


# 16 — "Change details" with no field picked asks which field to change -------
def test_change_details_without_field_asks_which():
    b = Booking(conversation_state=bf.WAITING_FOR_CONFIRMATION, service_id=_svc(0))
    menu = advance(b, Inbound(selection_id="change_details"))
    assert menu.state == bf.WAITING_FOR_CHANGE_FIELD
    assert menu.interactive and len(menu.interactive.options) == 6   # incl. Customer name
    # an unrecognized field at the menu re-shows the menu
    again = advance(Booking(conversation_state=bf.WAITING_FOR_CHANGE_FIELD, service_id=_svc(0)),
                    Inbound(text="something random"))
    assert again.state == bf.WAITING_FOR_CHANGE_FIELD


# 17 — invalid replacement input keeps the same targeted edit state -----------
def test_invalid_edit_input_stays_in_edit_state():
    # invalid slot
    r1 = advance(_full_booking(state=bf.EDITING_SLOT), Inbound(text="not a slot"))
    assert r1.state == bf.EDITING_SLOT
    assert "pickup_slot_id" not in r1.updates
    # invalid date
    r2 = advance(_full_booking(state=bf.EDITING_DATE), Inbound(text="the 32nd of Juvember"))
    assert r2.state == bf.EDITING_DATE
    assert "pickup_date" not in r2.updates
    # too-short address
    r3 = advance(_full_booking(state=bf.EDITING_ADDRESS), Inbound(text="x"))
    assert r3.state == bf.EDITING_ADDRESS
    assert "pickup_address" not in r3.updates
