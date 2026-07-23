"""Customer-name collection tests (spec: "Fix the customer-name collection
logic"). Hermetic — the FSM is exercised directly with an injected slots fake.
The DB-side pieces (profile name stored on customers.display_name, per-order
customer_name snapshot, verified-name lookup) are wired in the webhook/repo and
verified in staging; here we pin the deterministic name logic.
"""
import asyncio
import datetime as _dt

from services import booking_flow as bf
from services.booking_flow import Booking, Inbound

TODAY = _dt.date(2026, 7, 22)
_SLOTS = [{"slot_id": "morning_08_11", "label": "8–11 AM",
           "start_time": _dt.time(8), "end_time": _dt.time(11)}]


async def _slots(*_a, **_k):
    return list(_SLOTS)


def advance(b, inbound):
    return asyncio.run(bf.advance(b, inbound, today=TODAY, available_slots=_slots))


def _svc(i=0):
    from rules import active_service_catalog
    return active_service_catalog()[i]["service_id"]


def _full(**over):
    base = dict(conversation_state=bf.WAITING_FOR_CONFIRMATION, customer_name="Sara Ahmed",
                service_id=_svc(0), service_name_snapshot="Premium Wash & Fold",
                pickup_date=TODAY + _dt.timedelta(days=2), pickup_slot_id="morning_08_11",
                pickup_slot_label="8–11 AM", pickup_address="Marina Heights, Dubai Marina",
                pickup_instruction_code="none")
    base.update(over)
    return Booking(**base)


# The name step is now reached AFTER item collection (category -> item(s) ->
# name -> date -> …). This drives a draft with one collected item to the point
# where the FSM asks for the name.
_LINE = [{"item_code": "WASH_FOLD_6KG", "quantity": 1, "line_kind": "exact"}]


def _items_done(**over):
    b = Booking(conversation_state=bf.WAITING_FOR_MORE_ITEMS, service_id="WASH_FOLD",
                service_name_snapshot="Wash & Fold", line_items=list(_LINE), **over)
    return advance(b, Inbound(selection_id="items_done"))


# --- name validation ---------------------------------------------------------
def test_validate_name_accepts_international_names():
    for ok in ["Sara", "Amaan Patel", "Mary Jane", "Abdul-Rahman", "O'Connor",
               "  Fatima  "]:
        assert bf.validate_name(ok), ok
    assert bf.validate_name("  Sara  ") == "Sara"


def test_validate_name_rejects_blank_numeric_and_commands():
    for bad in ["", "   ", "12345", ".,-", "!!!", "yes", "confirm", "today", None,
                "x" * 60]:
        assert bf.validate_name(bad) is None, bad


# 1 — name in the first message is extracted ----------------------------------
def test_extract_name_from_first_message():
    assert bf.extract_name("My name is Sara.") == "Sara"
    assert bf.extract_name("This is Ahmed.") == "Ahmed"
    assert bf.extract_name("Book it under Amaan Patel.") == "Amaan Patel"


# 2 — name plus several other fields in one message ---------------------------
def test_extract_name_with_other_fields():
    assert bf.extract_name(
        "I need dry cleaning tomorrow. I'm Fatima and pickup is from JVC.") == "Fatima"
    assert bf.extract_name("I'm Ahmed. I need shoe cleaning tomorrow from Marina Heights.") == "Ahmed"


def test_extract_name_absent_returns_none():
    assert bf.extract_name("I need a laundry pickup") is None
    assert bf.extract_name("tomorrow at 5pm") is None


# 3 — the agent asks for the name when it is missing (no profile) --------------
def test_agent_asks_for_name_when_missing():
    reply = _items_done()                                # items collected, no name yet
    assert reply.state == bf.WAITING_FOR_NAME
    assert "name" in reply.text.lower()
    assert "customer_name" not in reply.updates          # nothing saved yet


# 4 — after the name is stored it is not asked again --------------------------
def test_name_not_reasked_after_stored():
    saved = advance(Booking(conversation_state=bf.WAITING_FOR_NAME, service_id="WASH_FOLD",
                            service_name_snapshot="Wash & Fold", line_items=list(_LINE)),
                    Inbound(text="Sara"))
    assert saved.updates["customer_name"] == "Sara"
    assert saved.state == bf.WAITING_FOR_PICKUP_DATE      # moves on, name done
    # a draft whose items are collected AND that already has a name skips the name step
    nxt = _items_done(customer_name="Sara")
    assert nxt.state == bf.WAITING_FOR_PICKUP_DATE


# 5/6 — profile name is offered, NOT auto-confirmed ---------------------------
def test_profile_name_offered_not_auto_saved():
    reply = _items_done(whatsapp_profile_name="Humaid")
    assert reply.state == bf.WAITING_FOR_NAME_CONFIRM     # asks to confirm, doesn't save
    assert "Humaid" in reply.text
    assert "customer_name" not in reply.updates


# 7 — the customer can confirm the profile name -------------------------------
def test_confirm_profile_name():
    b = Booking(conversation_state=bf.WAITING_FOR_NAME_CONFIRM, service_id="WASH_FOLD",
                service_name_snapshot="Wash & Fold", line_items=list(_LINE),
                whatsapp_profile_name="Humaid")
    reply = advance(b, Inbound(selection_id="name_use"))
    assert reply.updates["customer_name"] == "Humaid"
    assert reply.state == bf.WAITING_FOR_PICKUP_DATE


# 8 — the customer can enter a different name ---------------------------------
def test_enter_different_name():
    b = Booking(conversation_state=bf.WAITING_FOR_NAME_CONFIRM, service_id=_svc(0),
                service_name_snapshot="Premium Wash & Fold", whatsapp_profile_name="Humaid")
    changed = advance(b, Inbound(selection_id="name_change"))
    assert changed.state == bf.WAITING_FOR_NAME
    assert "customer_name" not in changed.updates
    typed = advance(Booking(conversation_state=bf.WAITING_FOR_NAME, service_id=_svc(0),
                            service_name_snapshot="Premium Wash & Fold"),
                    Inbound(text="Amaan Patel"))
    assert typed.updates["customer_name"] == "Amaan Patel"


# 9 — an existing verified name is offered for reuse and confirmed ------------
def test_verified_name_reused_after_confirmation():
    prompt = _items_done(verified_name="Sara")
    assert prompt.state == bf.WAITING_FOR_NAME_CONFIRM
    assert "Sara" in prompt.text
    used = advance(Booking(conversation_state=bf.WAITING_FOR_NAME_CONFIRM, service_id="WASH_FOLD",
                           service_name_snapshot="Wash & Fold", line_items=list(_LINE),
                           verified_name="Sara"),
                   Inbound(selection_id="name_use"))
    assert used.updates["customer_name"] == "Sara"


# 10 — a missing name blocks the final summary/confirmation --------------------
def test_missing_name_blocks_confirmation():
    # everything filled (incl. items) EXCEPT the name -> next step is the name
    b = Booking(service_id="WASH_FOLD", service_name_snapshot="Wash & Fold",
                line_items=list(_LINE),
                pickup_date=TODAY, pickup_slot_id="morning_08_11", pickup_slot_label="8–11 AM",
                pickup_address="Marina Heights", pickup_instruction_code="none")
    r = asyncio.run(bf.next_prompt_for(b, _slots))
    assert r.state in (bf.WAITING_FOR_NAME, bf.WAITING_FOR_NAME_CONFIRM)
    assert r.state != bf.WAITING_FOR_CONFIRMATION


# 11 — the name is present in the summary once collected ----------------------
def test_name_appears_in_summary():
    from services.booking_flow import _summary_text
    assert "Sara Ahmed" in _summary_text(_full())
    # a draft with no name yet shows a clear pending marker, not an invented name
    assert "Name pending" in _summary_text(_full(customer_name=None))


# 12 — the name survives a targeted edit of a DIFFERENT field ------------------
def test_name_preserved_when_editing_other_field():
    reply = advance(_full(conversation_state=bf.EDITING_SLOT),
                    Inbound(selection_id="slot:morning_08_11"))
    assert reply.state == bf.WAITING_FOR_CONFIRMATION
    assert "customer_name" not in reply.updates           # untouched
    assert "Sara Ahmed" in reply.text


# 13 — changing the name preserves every other field --------------------------
def test_change_name_preserves_everything_else():
    # Change details -> Customer name enters the targeted edit
    menu = advance(_full(conversation_state=bf.WAITING_FOR_CHANGE_FIELD),
                   Inbound(selection_id="change:name"))
    assert menu.state == bf.EDITING_NAME
    edited = advance(_full(conversation_state=bf.EDITING_NAME),
                     Inbound(text="Fatima Al Mansoori"))
    assert edited.state == bf.WAITING_FOR_CONFIRMATION
    assert edited.updates == {"customer_name": "Fatima Al Mansoori"}   # ONLY the name
    assert "Marina Heights, Dubai Marina" in edited.text
    assert "Premium Wash & Fold" in edited.text


# 16 — invalid/blank name at the name step is rejected and re-asked -----------
def test_invalid_name_rejected_and_reasked():
    r = advance(Booking(conversation_state=bf.WAITING_FOR_NAME, service_id=_svc(0)),
                Inbound(text="12345"))
    assert r.state == bf.WAITING_FOR_NAME
    assert "customer_name" not in r.updates


# 15/17 — two conversations keep independent names ----------------------------
def test_two_conversations_independent_names():
    a = advance(Booking(conversation_state=bf.WAITING_FOR_NAME, service_id=_svc(0),
                        service_name_snapshot="Premium Wash & Fold"), Inbound(text="Sara"))
    b = advance(Booking(conversation_state=bf.WAITING_FOR_NAME, service_id=_svc(1),
                        service_name_snapshot="Boutique Clean & Press"), Inbound(text="Ahmed"))
    assert a.updates["customer_name"] == "Sara"
    assert b.updates["customer_name"] == "Ahmed"
    assert a.updates["customer_name"] != b.updates["customer_name"]
