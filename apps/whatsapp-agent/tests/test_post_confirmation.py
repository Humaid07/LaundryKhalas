"""Post-confirmation terminal boundary (services/post_confirmation.py) +
run_booking_turn's confirmed-state block.

Proves the reported bug is fixed: once an order is confirmed the flow is a hard
stop — a stale/duplicate "yes", a bare ack, or empty noise never runs a booking
turn, and even an explicit follow-up sees an ORDER_CONFIRMED state (not a fresh
"new" booking that invites discount/upsell/re-confirm chatter).
"""
import datetime as _dt

from agents.whatsapp_agent import booking_tools
from agents.whatsapp_agent.booking_tools import (
    BookingContext,
    confirmed_state_block,
)
from services import order_store
from services import post_confirmation as pc
from services.post_confirmation import PostConfirmTurn as T


# --- classifier ------------------------------------------------------------
def test_bare_confirmation_echo_after_confirmed_is_noop():
    for t in ("yes", "Yes", "yes please", "confirm", "confirmed", "go ahead", "ok confirm"):
        assert pc.classify_post_confirmation_turn(t) is T.NONE, t


def test_gratitude_is_thanks_even_with_a_name():
    for t in ("thanks", "Thank you!", "thanks Shinu", "ok", "cheers"):
        assert pc.classify_post_confirmation_turn(t) is T.THANKS, t


def test_empty_or_bare_selection_is_noop():
    assert pc.classify_post_confirmation_turn("") is T.NONE
    assert pc.classify_post_confirmation_turn(None) is T.NONE
    assert pc.classify_post_confirmation_turn("", selection_id="confirm_booking") is T.NONE


def test_explicit_new_requests_are_actionable():
    assert pc.classify_post_confirmation_turn("Can I change the pickup time?") is T.QUERY
    assert pc.classify_post_confirmation_turn("change pickup time") is T.EDIT
    assert pc.classify_post_confirmation_turn("Add two trousers") is T.EDIT
    assert pc.classify_post_confirmation_turn("Why didn't I get a discount?") is T.QUERY
    assert pc.classify_post_confirmation_turn("place another order") is T.NEW_ORDER
    for phrase in ("Can I change the pickup time?", "Add two trousers",
                   "Why didn't I get a discount?", "place another order"):
        assert pc.classify_post_confirmation_turn(phrase).is_actionable, phrase


def test_thanks_and_none_are_not_actionable():
    assert not pc.classify_post_confirmation_turn("yes").is_actionable
    assert not pc.classify_post_confirmation_turn("thanks").is_actionable


# --- is_confirmed_order ----------------------------------------------------
def test_is_confirmed_order_by_status():
    assert pc.is_confirmed_order({"status": order_store.PICKUP_SCHEDULED}) is True
    assert pc.is_confirmed_order({"status": order_store.COMPLETED}) is True
    assert pc.is_confirmed_order({"status": order_store.DRAFT}) is False
    assert pc.is_confirmed_order({"status": order_store.CANCELLED}) is False
    assert pc.is_confirmed_order({"status": order_store.ABANDONED}) is False
    assert pc.is_confirmed_order(None) is False


def test_is_confirmed_order_by_post_order_state():
    from services import booking_flow as bf
    assert pc.is_confirmed_order(
        {"status": order_store.DRAFT, "conversation_state": bf.POST_ORDER}) is True


# --- confirmed_state_block -------------------------------------------------
def test_confirmed_state_block_is_terminal_and_complete():
    row = {
        "order_id": "LK-2026-000006", "status": order_store.PICKUP_SCHEDULED,
        "service_name_snapshot": "Wash & Fold", "pickup_date": _dt.date(2026, 7, 29),
        "pickup_slot": "5:00 PM – 8:00 PM", "pickup_area": "Al Nahda 2",
        "estimated_total": 27,
    }
    b = confirmed_state_block(row)
    assert b["workflow_state"] == "ORDER_CONFIRMED"
    assert b["booking_status"] == "CONFIRMED"
    assert b["automation_state"] == "IDLE"
    assert b["pending_confirmation"] is False
    assert b["active_booking_complete"] is True
    assert b["missing_fields"] == []
    assert b["ready_to_confirm"] is False
    assert b["order_number"] == "LK-2026-000006"
    assert b["order"]["final_price_aed"] == 27.0


# --- run_booking_turn feeds the confirmed block (no re-book) ----------------
class _ConfirmedRepo:
    """No active draft, but a CONFIRMED latest order."""

    def __init__(self):
        self.confirmed = {
            "id": "o1", "order_id": "LK-2026-000006", "status": order_store.PICKUP_SCHEDULED,
            "service_name_snapshot": "Wash & Fold", "pickup_date": _dt.date(2026, 7, 29),
            "pickup_slot": "5:00 PM – 8:00 PM", "pickup_area": "Al Nahda 2", "estimated_total": 27,
        }

    async def get_active_draft(self, conversation_id):
        return None

    async def get_latest_for_conversation(self, conversation_id):
        return self.confirmed


async def _slots(pickup_date, area, service_id):
    return [{"slot_id": "s1", "label": "9am – 12pm"}]


async def test_run_booking_turn_uses_confirmed_block_when_no_draft(monkeypatch):
    from llm import service as llm_service
    from llm.providers.base import LLMResult

    captured = {}

    async def _fake_complete(messages, *, tools, executor, max_tokens):
        captured["messages"] = messages
        return LLMResult(text="Your order total was AED 27.", provider="mock", model="m"), 1, True, None

    monkeypatch.setattr(llm_service, "complete_with_tools", _fake_complete)

    ctx = BookingContext(
        conversation_id="conv-pc", order_uuid=None, repo=_ConfirmedRepo(),
        today=_dt.date(2026, 7, 28), available_slots=_slots)
    reply, result = await booking_tools.run_booking_turn(ctx, text="why didn't I get a discount?")

    sys_texts = " ".join(m.content for m in captured["messages"] if m.role == "system")
    assert "ORDER_CONFIRMED" in sys_texts              # model told the booking is DONE
    assert '"workflow_state": "new"' not in sys_texts  # NOT a fresh booking
    assert reply                                        # a normal reply still comes back
