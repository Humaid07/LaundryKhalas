"""Slice-3 additions to the Claude booking tools: pickup-slots / customer-record /
saved-addresses / start-another-order read+write tools, and the create_complaint /
create_pending_task write tools. Runs offline against a fake repo; the two
DB-backed tools are exercised with monkeypatched repos.
"""
import datetime as _dt
import json

from agents.whatsapp_agent.booking_tools import BookingContext, make_booking_executor
from db.repositories import complaints_repo, pending_tasks_repo
from services import booking_flow as bf
from services import order_store


class FakeRepo:
    def __init__(self):
        self.conversation_id = "conv-1"
        self.row = {
            "id": "o1", "order_id": "LK-2026-000999", "conversation_id": "conv-1",
            "status": order_store.DRAFT, "conversation_state": bf.WAITING_FOR_SERVICE,
            "pickup_date": _dt.date(2026, 7, 28), "pickup_area": "Dubai Marina",
        }
        self.start_booking_calls = 0

    async def get_active_draft(self, cid):
        return self.row if self.row["status"] == order_store.DRAFT else None

    async def start_booking(self, cid, customer):
        self.start_booking_calls += 1
        self.row = {"id": "o2", "order_id": "LK-2026-001000", "conversation_id": cid,
                    "status": order_store.DRAFT, "conversation_state": bf.WAITING_FOR_SERVICE}
        return self.row

    async def apply_booking_updates(self, uid, updates, state):
        self.row.update({k: v for k, v in (updates or {}).items() if not k.startswith("_")})
        self.row["conversation_state"] = state
        return self.row


async def _slots(date, area, service_id):
    return [{"slot_id": "s1", "label": "9am – 12pm"}, {"slot_id": "s2", "label": "2pm – 5pm"}]


def _ctx(customer=None):
    repo = FakeRepo()
    ctx = BookingContext(
        conversation_id="conv-1", order_uuid="o1", repo=repo, today=_dt.date(2026, 7, 25),
        available_slots=_slots, customer=customer or {"id": "cust-1", "area": "Dubai Marina",
                                                      "city": "Dubai", "market": "AE"},
        verified_name="Sara")
    return ctx, repo, make_booking_executor(ctx)


async def _call(execute, name, ti=None):
    out, is_err = await execute(name, ti or {})
    return json.loads(out), is_err


# --------------------------- read tools ----------------------------------
async def test_get_available_pickup_slots_uses_draft_date():
    _, _, execute = _ctx()
    data, err = await _call(execute, "get_available_pickup_slots")
    assert not err
    # Rich, backend-authoritative output: timezone + current datetime + filtered windows.
    assert data["timezone"] == "Asia/Dubai"
    assert "current_local_datetime" in data and "minimum_lead_time_minutes" in data
    assert [s["label"] for s in data["available_slots"]] == ["9am – 12pm", "2pm – 5pm"]


async def test_get_available_pickup_slots_falls_back_on_unparseable_date():
    # An unrecognised date_text degrades gracefully to the draft's date (no error).
    _, _, execute = _ctx()
    data, err = await _call(execute, "get_available_pickup_slots", {"date_text": "whenever"})
    assert not err
    assert [s["label"] for s in data["available_slots"]] == ["9am – 12pm", "2pm – 5pm"]


async def test_get_customer_record_is_pii_safe():
    _, _, execute = _ctx(customer={"id": "c", "area": "JVC", "city": "Dubai",
                                   "phone_e164": "+971500000000", "market": "AE"})
    data, err = await _call(execute, "get_customer_record")
    assert not err
    assert data["confirmed_name"] == "Sara" and data["returning_customer"] is True
    assert data["area"] == "JVC"
    # No phone/email ever surfaced.
    assert "phone" not in json.dumps(data) and "+9715" not in json.dumps(data)


async def test_get_saved_addresses_returns_saved_then_area():
    _, _, execute = _ctx(customer={"id": "c", "area": "JVC", "address": "Villa 3, JVC"})
    data, _ = await _call(execute, "get_saved_addresses")
    assert data["saved_addresses"][0]["address"] == "Villa 3, JVC"

    _, _, execute2 = _ctx(customer={"id": "c", "area": "JVC"})  # no full address
    data2, _ = await _call(execute2, "get_saved_addresses")
    assert data2["saved_addresses"][0]["label"] == "area"


async def test_start_another_order_creates_fresh_draft():
    _, repo, execute = _ctx()
    data, err = await _call(execute, "start_another_order")
    assert not err and data["started"] is True
    assert repo.start_booking_calls == 1
    assert data["workflow"]["order_number"] == "LK-2026-001000"


# --------------------------- DB-backed write tools -----------------------
async def test_create_complaint_logs_and_tasks(monkeypatch):
    created = {}

    async def fake_complaint(**kw):
        created["complaint"] = kw
        return {"id": "cmp-1", "complaint_ref": "CMP-ABCD1234"}

    async def fake_task(task_type, **kw):
        created["task"] = (task_type, kw)
        return {"id": "t1", "task_ref": "TSK-1"}

    monkeypatch.setattr(complaints_repo, "create", fake_complaint)
    monkeypatch.setattr(pending_tasks_repo, "create", fake_task)

    _, _, execute = _ctx()
    data, err = await _call(execute, "create_complaint",
                            {"description": "my shirt came back torn", "order_ref": "LK-2026-000001"})
    assert not err and data["complaint_created"] is True
    assert data["reference"] == "CMP-ABCD1234"
    # Classified as damage; never promises compensation in the guidance.
    assert created["complaint"]["category"] == "damage"
    assert "refund" not in data["message"].lower() or "do not promise" in data["message"].lower()
    # A review task was opened.
    assert created["task"][0] == "AWAITING_COMPLAINT_REVIEW"


async def test_create_pending_task_validates_type(monkeypatch):
    async def fake_task(task_type, **kw):
        return {"id": "t1", "task_ref": "TSK-9", "task_type": task_type}

    monkeypatch.setattr(pending_tasks_repo, "create", fake_task)
    _, _, execute = _ctx()

    ok, err = await _call(execute, "create_pending_task", {"task_type": "AWAITING_FACILITY_QUOTE"})
    assert not err and ok["task_created"] is True

    bad, err2 = await _call(execute, "create_pending_task", {"task_type": "AWAITING_UNICORN"})
    assert err2  # unknown type rejected


# --------------------------- alias fix -----------------------------------
def test_shortening_resolves_to_alterations():
    code, reason = bf.resolve_service(bf.Inbound(text="shortening"))
    assert reason == "ok"
    from services import catalogue
    assert catalogue.category_by_code(code)["code"] == "ALTERATIONS"
