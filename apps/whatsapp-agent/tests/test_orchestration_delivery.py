"""Claude-orchestrated conversation: lazy order creation, grounded Q&A without a
draft, and the empty-reply guard so the customer is never left in silence
(task spec §§1-2, 9, 29). Runs fully offline against a fake repo + a scripted
provider — the backend controls every mutation.
"""
import datetime as _dt
import json

import pytest

from agents.whatsapp_agent import booking_tools
from agents.whatsapp_agent.booking_tools import BookingContext, make_booking_executor
from services import booking_flow as bf
from services import order_store


class LazyFakeRepo:
    """Starts with NO draft; start_booking creates one lazily (idempotent)."""

    def __init__(self, conversation_id):
        self.conversation_id = conversation_id
        self.row = None
        self.start_calls = 0

    async def get_active_draft(self, conversation_id):
        return self.row if (self.row and self.row["status"] == order_store.DRAFT) else None

    async def start_booking(self, conversation_id, customer):
        self.start_calls += 1
        if self.row is None:
            self.row = {"id": "order-uuid-1", "order_id": "LK-2026-000123",
                        "conversation_id": conversation_id, "status": order_store.DRAFT,
                        "conversation_state": bf.WAITING_FOR_SERVICE}
        return self.row

    async def apply_booking_updates(self, order_uuid, updates, state):
        data = dict(updates or {})
        data.pop("_touch_service_selected_at", None)
        self.row.update(data)
        self.row["conversation_state"] = state
        return self.row

    async def confirm_booking(self, order_uuid):
        if self.row["status"] != order_store.DRAFT:
            return self.row, False
        self.row["status"] = order_store.PICKUP_SCHEDULED
        return self.row, True

    async def set_conversation_state(self, order_uuid, state):
        self.row["conversation_state"] = state
        return self.row

    async def get_latest_for_conversation(self, conversation_id):
        return self.row


async def _slots(pickup_date, emirate, service_id):
    return [{"slot_id": "s1", "label": "9am – 12pm"}]


def _ctx(repo):
    return BookingContext(
        conversation_id=repo.conversation_id, order_uuid=None, repo=repo,
        today=_dt.date(2026, 7, 26), available_slots=_slots, customer={"id": "c1"})


async def _call(execute, tool, **inp):
    text, is_error = await execute(tool, inp)
    return json.loads(text), is_error


# --- Grounded Q&A must NOT create an order (spec §1/§9) ----------------------
async def test_price_question_does_not_create_a_draft():
    repo = LazyFakeRepo("conv-q")
    execute = make_booking_executor(_ctx(repo))
    data, err = await _call(execute, "lookup_item_price", query="sneaker cleaning")
    assert err is False
    assert repo.start_calls == 0 and repo.row is None    # no order created by a question


async def test_turnaround_question_does_not_create_a_draft():
    repo = LazyFakeRepo("conv-t")
    execute = make_booking_executor(_ctx(repo))
    _, err = await _call(execute, "estimate_turnaround", query="wash and fold")
    assert err is False
    assert repo.row is None


# --- Booking write lazily creates the draft ---------------------------------
async def test_first_write_tool_lazily_creates_the_draft():
    repo = LazyFakeRepo("conv-w")
    execute = make_booking_executor(_ctx(repo))
    data, err = await _call(execute, "save_customer_name", name="Amaan")
    assert err is False and data["customer_name"] == "Amaan"
    assert repo.start_calls == 1 and repo.row is not None


# --- confirm_order is guarded (injection defense, spec §9) ------------------
async def test_confirm_rejected_while_fields_missing():
    repo = LazyFakeRepo("conv-c")
    execute = make_booking_executor(_ctx(repo))
    await _call(execute, "save_customer_name", name="Amaan")   # only a name so far
    data, err = await _call(execute, "confirm_order")
    assert err is True and "missing" in data["error"].lower()


# --- Scripted-provider helpers ----------------------------------------------
class _Blk:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _Usage:
    input_tokens = output_tokens = 5
    cache_read_input_tokens = cache_creation_input_tokens = 0


class _Resp:
    def __init__(self, content, stop):
        self.content, self.stop_reason, self.usage = content, stop, _Usage()
        self._request_id = "req_x"


def _script_provider(monkeypatch, script):
    from llm import service as llm_service
    from llm.providers.anthropic import AnthropicProvider

    class _FakeMessages:
        async def create(self, **kw):
            return script.pop(0)

    class _FakeClient:
        messages = _FakeMessages()

    provider = AnthropicProvider("k", "claude-opus-4-8", client=_FakeClient())
    monkeypatch.setattr(llm_service, "_select_provider", lambda: provider)


# --- Empty-reply guard: never send silence (spec §2/§29) --------------------
async def test_empty_model_text_is_replaced_with_grounded_next_step(monkeypatch):
    _script_provider(monkeypatch, [_Resp([_Blk(type="text", text="")], "end_turn")])
    repo = LazyFakeRepo("conv-empty")
    reply, result = await booking_tools.run_booking_turn(_ctx(repo), text="hi")
    assert reply and reply.strip()                       # never empty
    assert "clean" in reply.lower()                      # grounded next step
    assert repo.row is None                              # a bare 'hi' created no order


async def test_model_requested_human_support_is_recorded(monkeypatch):
    _script_provider(monkeypatch, [
        _Resp([_Blk(type="tool_use", name="request_human_support",
                    input={"reason": "complaint"}, id="t1")], "tool_use"),
        _Resp([_Blk(type="text", text="I've flagged this to our team.")], "end_turn"),
    ])
    repo = LazyFakeRepo("conv-esc")
    ctx = _ctx(repo)
    reply, result = await booking_tools.run_booking_turn(ctx, text="this is a complaint")
    assert "request_human_support" in ctx.tool_calls
    assert reply.strip()
