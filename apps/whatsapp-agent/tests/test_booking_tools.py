"""Claude-orchestrated booking write-tools (agents/whatsapp_agent/booking_tools.py).

Runs fully offline against a fake persistence adapter (no DB) — the real
validators (services/booking_flow resolvers + catalogue/pricing) do the work, so
these prove the backend, not the model, controls every mutation.
"""
import datetime as _dt
import json

import pytest

from agents.whatsapp_agent import booking_tools
from agents.whatsapp_agent.booking_tools import (
    BookingContext,
    make_booking_executor,
    workflow_state_block,
)
from services import booking_flow as bf
from services import catalogue, order_store


@pytest.fixture(autouse=True)
def spy_post_confirm(monkeypatch):
    """Keep these tests offline AND observable: replace the first-confirm
    side-effects helper (facility assign / notify / campaign / CRM — all hit the
    real DB) with an in-memory spy. Returns the list of (order_row, customer_id)
    it was called with, so a test can assert the Claude confirm path wires it."""
    calls: list[tuple[dict, object]] = []

    async def _spy(order_row, customer_id):
        calls.append((order_row, customer_id))
        return None

    monkeypatch.setattr(
        booking_tools.order_confirmation, "apply_post_confirmation_effects", _spy
    )
    return calls


# --- Fake persistence adapter (mirrors orders_repo's surface) ---------------
class FakeOrdersRepo:
    def __init__(self, conversation_id):
        self.conversation_id = conversation_id
        self.row = {
            "id": "order-uuid-1",
            "order_id": "LK-2026-000999",
            "conversation_id": conversation_id,
            "status": order_store.DRAFT,
            "conversation_state": bf.WAITING_FOR_SERVICE,
        }
        self.confirm_calls = 0

    async def get_active_draft(self, conversation_id):
        return self.row if self.row["status"] == order_store.DRAFT else None

    async def apply_booking_updates(self, order_uuid, updates, state):
        data = dict(updates or {})
        data.pop("_touch_service_selected_at", None)
        self.row.update(data)
        self.row["conversation_state"] = state
        return self.row

    async def confirm_booking(self, order_uuid):
        self.confirm_calls += 1
        if self.row["status"] != order_store.DRAFT:
            return self.row, False          # idempotent: already confirmed
        self.row["status"] = order_store.PICKUP_SCHEDULED
        self.row["conversation_state"] = "booking_confirmed"
        return self.row, True

    async def set_conversation_state(self, order_uuid, state):
        self.row["conversation_state"] = state
        return self.row

    async def get_latest_for_conversation(self, conversation_id):
        return self.row


async def _slots(pickup_date, emirate, service_id):
    return [{"slot_id": "s1", "label": "9am – 12pm"}, {"slot_id": "s2", "label": "2pm – 5pm"}]


def _ctx(repo):
    return BookingContext(
        conversation_id=repo.conversation_id, order_uuid=repo.row["id"], repo=repo,
        today=_dt.date(2026, 7, 25), available_slots=_slots,
    )


def _pick_category_and_item():
    """A category + a non-measured item that both resolve unambiguously — chosen
    from the live catalogue so the test isn't brittle to catalogue edits."""
    for c in catalogue.categories():
        code, reason = bf.resolve_service(bf.Inbound(text=c["name"]))
        if reason != "ok" or code != c["code"]:
            continue
        for it in catalogue.items_for_category(c["code"]):
            if it.get("requires_measurement"):
                continue
            icode, ireason = bf.resolve_item(bf.Inbound(text=it["canonical_name"]), None, c["code"])
            if ireason == "ok" and icode == it["item_code"]:
                return c, it
    return None, None


async def _call(execute, tool, **inp):
    text, is_error = await execute(tool, inp)
    return json.loads(text), is_error


# --- Tests -----------------------------------------------------------------
async def test_full_booking_via_write_tools_then_idempotent_confirm():
    category, item = _pick_category_and_item()
    if not category:
        pytest.skip("no unambiguous category/item pair in the catalogue")
    repo = FakeOrdersRepo("conv-1")
    execute = make_booking_executor(_ctx(repo))

    data, err = await _call(execute, "save_customer_name", name="Sara Ahmed")
    assert err is False and data["customer_name"] == "Sara Ahmed"

    data, err = await _call(execute, "save_service_selection", service=category["name"])
    assert err is False and data["category_code"] == category["code"]

    data, err = await _call(execute, "save_order_item", item=item["canonical_name"], quantity=3)
    assert err is False and data["quantity"] == 3
    assert repo.row["line_items"]  # backend recomputed + persisted the priced line

    data, err = await _call(execute, "save_pickup_date", date_text="tomorrow")
    assert err is False and data["pickup_date"] == "2026-07-26"

    data, err = await _call(execute, "save_pickup_time", slot="1")
    assert err is False and data["pickup_time_window"] == "9am – 12pm"

    data, err = await _call(execute, "save_pickup_address", address="Villa 12, Dubai Marina")
    assert err is False and data["area_recognised"] == "Dubai Marina"

    wf, err = await _call(execute, "get_current_workflow")
    assert err is False and wf["workflow"]["ready_to_confirm"] is True
    assert wf["workflow"]["missing_fields"] == []

    data, err = await _call(execute, "confirm_order")
    assert err is False and data["confirmed"] is True and data["created_now"] is True

    # Idempotency: a repeated confirm (duplicate model request) creates no 2nd
    # order — the executor reports the existing one without a second real confirm.
    data, err = await _call(execute, "confirm_order")
    assert data["created_now"] is False
    assert repo.confirm_calls == 1
    assert repo.row["status"] == order_store.PICKUP_SCHEDULED


async def test_calculate_applicable_order_discount_tool_carpet_600():
    """The authoritative discount tool: for a 30 sqm carpet estimate (AED 600)
    with a discount request it returns the 20% tier (AED 120 off → AED 480),
    labels it ESTIMATED, and PERSISTS AED 480 as the draft's final total."""
    repo = FakeOrdersRepo("conv-disc")
    repo.row.update({
        "line_items": [{"item_code": "HOME_CARE_CARPET_REGULAR_SQM", "quantity": 1,
                        "measure": 30, "line_kind": "estimate"}],
        "catalogue_category_code": "HOME_CARE", "catalogue_category_name": "Home & Care",
        "discount_requested": False, "estimated_total": 600.0, "amount": 600.0,
    })
    execute = make_booking_executor(_ctx(repo))

    data, err = await _call(execute, "calculate_applicable_order_discount")
    assert err is False
    assert data["eligible"] is True
    assert data["applied_discount_rule_code"] == "ORDER_OVER_200_DISCOUNT_REQUESTED"
    assert data["applied_percentage"] == 20.0
    assert data["pre_discount_total"] == 600.0
    assert data["discount_amount"] == 120.0
    assert data["final_total"] == 480.0
    assert data["currency"] == "AED"
    assert data["pricing_status"] == "ESTIMATED"
    assert "480" in data["customer_safe_summary"] and "600" in data["customer_safe_summary"]

    # PERSISTED: the draft now stores AED 480 as the final total (not 600).
    assert repo.row["discount_requested"] is True
    assert repo.row["estimated_total"] == 480.0
    assert repo.row["amount"] == 480.0
    assert repo.row["discount_amount"] == 120.0

    # Idempotent: calling again does not stack — still 480.
    data2, _ = await _call(execute, "calculate_applicable_order_discount")
    assert data2["final_total"] == 480.0 and repo.row["estimated_total"] == 480.0


async def test_claude_confirm_triggers_post_confirmation_effects(spy_post_confirm):
    """The Claude `confirm_order` tool must run the SAME first-confirm side
    effects (facility auto-assign + notify, campaign attribution, CRM recompute)
    as the deterministic FSM path — once, on first confirm only. Regression for
    orders confirmed via natural language never reaching a facility."""
    category, item = _pick_category_and_item()
    if not category:
        pytest.skip("no unambiguous category/item pair in the catalogue")
    repo = FakeOrdersRepo("conv-eff")
    ctx = BookingContext(
        conversation_id=repo.conversation_id, order_uuid=repo.row["id"], repo=repo,
        today=_dt.date(2026, 7, 25), available_slots=_slots,
        customer={"id": "cust-uuid-9"},
    )
    execute = make_booking_executor(ctx)

    await _call(execute, "save_customer_name", name="Sara Ahmed")
    await _call(execute, "save_service_selection", service=category["name"])
    await _call(execute, "save_order_item", item=item["canonical_name"], quantity=3)
    await _call(execute, "save_pickup_date", date_text="tomorrow")
    await _call(execute, "save_pickup_time", slot="1")
    await _call(execute, "save_pickup_address", address="Villa 12, Dubai Marina")

    data, err = await _call(execute, "confirm_order")
    assert err is False and data["created_now"] is True
    # Ran exactly once, with the confirmed order row + the customer id.
    assert len(spy_post_confirm) == 1
    order_row, customer_id = spy_post_confirm[0]
    assert order_row["order_id"] == "LK-2026-000999"
    assert customer_id == "cust-uuid-9"

    # Duplicate confirm (idempotent) must NOT re-run the side effects.
    await _call(execute, "confirm_order")
    assert len(spy_post_confirm) == 1


async def test_confirm_rejected_when_fields_missing():
    repo = FakeOrdersRepo("conv-2")
    execute = make_booking_executor(_ctx(repo))
    data, err = await _call(execute, "confirm_order")
    assert err is True
    assert "missing" in data["error"].lower()
    # backend never confirmed
    assert repo.row["status"] == order_store.DRAFT


async def test_unknown_and_invalid_service_rejected():
    repo = FakeOrdersRepo("conv-3")
    execute = make_booking_executor(_ctx(repo))

    data, err = await _call(execute, "delete_all_orders")
    assert err is True and "Unknown tool" in data["error"]

    data, err = await _call(execute, "save_service_selection", service="spaceship engine repair")
    assert err is True
    assert repo.row.get("service_id") is None  # nothing persisted for an invalid service


async def test_item_rejected_before_service_selected():
    repo = FakeOrdersRepo("conv-4")
    execute = make_booking_executor(_ctx(repo))
    data, err = await _call(execute, "save_order_item", item="shirt", quantity=1)
    assert err is True
    assert "service" in data["error"].lower()


async def test_invalid_name_rejected():
    repo = FakeOrdersRepo("conv-5")
    execute = make_booking_executor(_ctx(repo))
    data, err = await _call(execute, "save_customer_name", name="!!!")
    assert err is True
    assert repo.row.get("customer_name") is None


async def test_past_date_rejected():
    repo = FakeOrdersRepo("conv-6")
    execute = make_booking_executor(_ctx(repo))
    data, err = await _call(execute, "save_pickup_date", date_text="01/01/2020")
    assert err is True
    assert repo.row.get("pickup_date") is None


async def test_run_booking_turn_drives_tools_via_provider(monkeypatch):
    """End-to-end: a scripted Claude provider calls the write-tools through
    run_booking_turn; the backend validates + persists each via the fake repo."""
    from llm import service as llm_service
    from llm.providers.anthropic import AnthropicProvider
    from agents.whatsapp_agent import booking_tools

    category, _ = _pick_category_and_item()
    if not category:
        pytest.skip("no unambiguous category in the catalogue")

    class _Blk:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    class _Usage:
        input_tokens = output_tokens = 10
        cache_read_input_tokens = cache_creation_input_tokens = 0

    class _Resp:
        def __init__(self, content, stop):
            self.content, self.stop_reason, self.usage = content, stop, _Usage()
            self._request_id = "req_x"

    def _tu(name, inp, i):
        return _Blk(type="tool_use", name=name, input=inp, id=i)

    script = [
        _Resp([_tu("save_customer_name", {"name": "Sara Ahmed"}, "t1")], "tool_use"),
        _Resp([_tu("save_service_selection", {"service": category["name"]}, "t2")], "tool_use"),
        _Resp([_Blk(type="text", text="Great — what would you like cleaned?")], "end_turn"),
    ]

    class _FakeMessages:
        async def create(self, **kw):
            return script.pop(0)

    class _FakeClient:
        messages = _FakeMessages()

    provider = AnthropicProvider("k", "claude-opus-4-8", client=_FakeClient())
    monkeypatch.setattr(llm_service, "_select_provider", lambda: provider)

    repo = FakeOrdersRepo("conv-orch")
    reply, result = await booking_tools.run_booking_turn(_ctx(repo), text="hi, book a pickup")

    assert "cleaned" in reply
    assert repo.row["customer_name"] == "Sara Ahmed"      # persisted via write-tool
    assert repo.row["service_id"] == category["code"]     # persisted via write-tool
    assert result.provider == "anthropic"


def test_workflow_state_block_hides_internal_ids():
    row = {
        "id": "secret-uuid", "order_id": "LK-2026-000999", "status": "draft",
        "conversation_state": "waiting_for_service", "customer_name": None,
    }
    block = workflow_state_block(row)
    assert "secret-uuid" not in json.dumps(block)   # internal UUID never exposed
    assert block["order_number"] == "LK-2026-000999"
    assert "customer_name" in block["missing_fields"]
