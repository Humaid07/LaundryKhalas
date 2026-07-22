"""Multiple-orders-per-conversation tests (spec: "Allow customers to place another
order after confirmation").

FSM-level and hermetic. The order-lifecycle pieces that require the database
(idempotent draft reuse, second-order creation, dashboard cards) are exercised by
the webhook layer against Supabase in staging — see the build report. Here we
pin the deterministic decision logic the webhook relies on.
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


# 14/15 — new-order intent is recognized (returning later, various phrasings) ---
def test_new_order_intent_recognized():
    for phrase in ["I want another pickup", "I need to place a new order",
                   "Book another laundry service", "place another order",
                   "I also need shoe cleaning", "start over"]:
        assert bf.is_new_order_intent(phrase) is True, phrase


def test_non_new_order_text_not_misread():
    for phrase in ["yes", "confirm", "Marina Heights villa 3", "today", "thanks"]:
        assert bf.is_new_order_intent(phrase) is False, phrase


# post-order next actions payload uses the stable action ids -------------------
def test_post_order_actions_payload():
    r = bf.post_order_actions()
    assert r.state == bf.POST_ORDER
    ids = [o.id for o in r.interactive.options]
    assert ids == [bf.NEW_ORDER, bf.CHECK_ORDER_STATUS, bf.HUMAN_SUPPORT]
    assert r.interactive.kind == "list"


def test_resolve_post_order_action_from_selection_and_numbered():
    assert bf.resolve_post_order_action(Inbound(selection_id=bf.NEW_ORDER)) == bf.NEW_ORDER
    # numbered mapping only when we know we're in the post-order context
    assert bf.resolve_post_order_action(Inbound(text="2"), numbered=True) == bf.CHECK_ORDER_STATUS
    assert bf.resolve_post_order_action(Inbound(text="1"), numbered=False) is None
    assert bf.resolve_post_order_action(Inbound(text="another pickup")) == bf.NEW_ORDER


# 4/7 — starting another order shows the service list and assumes NO service ----
def test_begin_new_order_asks_for_service_and_reuses_nothing():
    r = bf.begin_new_order()
    assert r.state == bf.WAITING_FOR_SERVICE
    assert r.interactive and r.interactive.kind == "list"
    assert "another order" in r.text.lower()
    assert "service_id" not in r.updates          # previous service NOT carried over


# 16 — an incomplete draft triggers the continue / start-new / cancel choice ----
def test_resume_or_new_prompt_and_choices():
    prompt = bf.resume_or_new_prompt()
    assert prompt.state == bf.RESUME_OR_NEW
    assert [o.id for o in prompt.interactive.options] == [
        "resume_continue", "resume_new", "resume_cancel"]

    # a draft mid-flow (address still missing) with progress made
    draft = Booking(conversation_state=bf.RESUME_OR_NEW, service_id=_svc(0),
                    customer_name="Sara", service_name_snapshot="Premium Wash & Fold",
                    pickup_date=TODAY + _dt.timedelta(days=1),
                    pickup_slot_id="morning_08_11", pickup_slot_label="8–11 AM")
    # continue -> restores the current step (address), does NOT restart
    cont = advance(draft, Inbound(selection_id="resume_continue"))
    assert cont.state == bf.WAITING_FOR_ADDRESS
    assert cont.start_new_order is False
    # start new -> signals the webhook to open a fresh workflow
    new = advance(draft, Inbound(selection_id="resume_new"))
    assert new.start_new_order is True
    assert new.confirm_now is False
    # cancel -> ends this draft
    cancel = advance(draft, Inbound(selection_id="resume_cancel"))
    assert cancel.cancel_now is True


def test_has_progress_detects_collected_fields():
    empty = Booking(conversation_state=bf.WAITING_FOR_SERVICE)
    started = Booking(conversation_state=bf.WAITING_FOR_PICKUP_DATE, service_id=_svc(0))
    assert bf.has_progress(empty) is False
    assert bf.has_progress(started) is True


# next_prompt_for re-derives the current step purely from filled fields ---------
def test_next_prompt_for_reconstructs_current_step():
    async def check(booking, expected_state):
        r = await bf.next_prompt_for(booking, _slots)
        assert r.state == expected_state

    asyncio.run(check(Booking(), bf.WAITING_FOR_SERVICE))
    asyncio.run(check(Booking(service_id=_svc(0)), bf.WAITING_FOR_NAME))   # name required next
    asyncio.run(check(Booking(service_id=_svc(0), customer_name="Sara"),
                      bf.WAITING_FOR_PICKUP_DATE))
    asyncio.run(check(Booking(service_id=_svc(0), customer_name="Sara", pickup_date=TODAY,
                              pickup_slot_id="morning_08_11", pickup_slot_label="8–11 AM"),
                      bf.WAITING_FOR_ADDRESS))
    asyncio.run(check(Booking(service_id=_svc(0), customer_name="Sara", pickup_date=TODAY,
                              pickup_slot_id="morning_08_11", pickup_slot_label="8–11 AM",
                              pickup_address="Villa 9, Barsha",
                              pickup_instruction_code="none"),
                      bf.WAITING_FOR_CONFIRMATION))


# 17 — two conversations keep independent workflow state (no shared globals) ----
def test_two_conversations_independent_state():
    a = advance(Booking(conversation_state=bf.WAITING_FOR_SERVICE),
                Inbound(selection_id=f"service:{_svc(0)}"))
    b_started = Booking(conversation_state=bf.RESUME_OR_NEW, service_id=_svc(1),
                        pickup_date=TODAY)
    b = advance(b_started, Inbound(selection_id="resume_new"))
    # A progressed its own booking; B independently asked to start new
    assert a.updates["service_id"] == _svc(0)
    assert b.start_new_order is True
    assert a.start_new_order is False


# a confirmed order stays confirmed (FSM never re-confirms / never restarts) ----
def test_confirmed_state_is_terminal_for_the_fsm():
    again = advance(Booking(conversation_state=bf.BOOKING_CONFIRMED, service_id=_svc(0)),
                    Inbound(text="thanks"))
    assert again.confirm_now is False
