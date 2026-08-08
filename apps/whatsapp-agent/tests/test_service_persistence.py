"""Service state survives the whole booking + unsupported-service handling.

Exercises the Claude write-tool executor (agents/whatsapp_agent/booking_tools.py)
against a fake persistence adapter — no DB, no model. Proves the reported bug is
fixed at the backend the model is forced to go through:

  * a saved service is never lost while scheduling pickup date/time;
  * "haircut" is classified UNSUPPORTED — the booking is preserved and the agent
    is pointed at the real next field, never re-asking which service;
  * an unsupported request with no booking creates no order;
  * a null/empty service can't erase a saved one;
  * the same service is never re-requested;
  * a bespoke request routes to the photo/quote flow, not an invented price.
"""
import datetime as _dt
import json

import pytest

from agents.whatsapp_agent.booking_tools import (
    BookingContext,
    make_booking_executor,
)
from services import booking_flow as bf
from services import catalogue, order_store


class FakeOrdersRepo:
    """Minimal orders_repo surface with patch-semantics apply (only the given
    columns change — exactly like the real whitelisted UPDATE)."""

    def __init__(self, row: dict | None = None):
        self.conversation_id = "conv-x"
        self.row = row
        self.start_calls = 0

    async def get_active_draft(self, conversation_id):
        if self.row and self.row.get("status", order_store.DRAFT) == order_store.DRAFT:
            return self.row
        return None

    async def start_booking(self, conversation_id, customer):
        self.start_calls += 1
        if self.row is None:
            self.row = {
                "id": "order-uuid-x", "order_id": "LK-2026-000777",
                "conversation_id": conversation_id, "status": order_store.DRAFT,
                "conversation_state": bf.WAITING_FOR_SERVICE,
            }
        return self.row

    async def apply_booking_updates(self, order_uuid, updates, state):
        assert self.row is not None
        data = dict(updates or {})
        data.pop("_touch_service_selected_at", None)
        self.row.update(data)          # PATCH — untouched columns are preserved
        self.row["conversation_state"] = state
        return self.row

    async def get_latest_for_conversation(self, conversation_id):
        return self.row

    async def set_conversation_state(self, order_uuid, state):
        self.row["conversation_state"] = state
        return self.row


async def _slots(pickup_date, area, service_id):
    return [{"slot_id": "s1", "label": "9am – 12pm"}, {"slot_id": "s2", "label": "2pm – 5pm"}]


def _ctx(repo):
    return BookingContext(
        conversation_id=repo.conversation_id, order_uuid="order-uuid-x", repo=repo,
        today=_dt.date(2026, 7, 25), available_slots=_slots)


async def _call(execute, tool, **inp):
    text, is_error = await execute(tool, inp)
    return json.loads(text), is_error


def _carpet_row(**extra):
    """A draft with Carpet Cleaning already saved + optional fields. Carpet Cleaning
    is now its own top-level category (CARPET_CLEANING), promoted out of HOME_CARE."""
    row = {
        "id": "order-uuid-x", "order_id": "LK-2026-000777",
        "conversation_id": "conv-x", "status": order_store.DRAFT,
        "conversation_state": bf.WAITING_FOR_PICKUP_SLOT,
        "service_id": "CARPET_CLEANING", "service": "Carpet Cleaning",
        "service_name_snapshot": "Carpet Cleaning", "line_items": [],
    }
    row.update(extra)
    return row


# --- service survives pickup scheduling ------------------------------------
async def test_saved_service_survives_pickup_date_and_time():
    repo = FakeOrdersRepo(_carpet_row(customer_name="Sara"))
    execute = make_booking_executor(_ctx(repo))

    d, err = await _call(execute, "save_pickup_date", date_text="tomorrow")
    assert err is False
    assert repo.row["service_id"] == "CARPET_CLEANING"            # not lost
    assert "service_items" not in d["workflow"]["missing_fields"]

    t, err = await _call(execute, "save_pickup_time", slot="1")
    assert err is False
    assert repo.row["service_id"] == "CARPET_CLEANING"            # still not lost
    missing = t["workflow"]["missing_fields"]
    assert "service_items" not in missing
    assert "pickup_address" in missing                      # the REAL next field


async def test_saved_service_survives_an_invalid_date_reply():
    repo = FakeOrdersRepo(_carpet_row(customer_name="Sara"))
    execute = make_booking_executor(_ctx(repo))
    d, err = await _call(execute, "save_pickup_date", date_text="yesterday")
    assert err is True                                      # politely rejected
    assert repo.row["service_id"] == "CARPET_CLEANING"            # preserved


# --- unsupported service (the screenshot bug) ------------------------------
async def test_haircut_during_active_booking_preserves_service_and_next_field():
    repo = FakeOrdersRepo(_carpet_row(
        customer_name="Sara", pickup_date=_dt.date(2026, 7, 26),
        pickup_slot="9am – 12pm", conversation_state=bf.WAITING_FOR_ADDRESS))
    execute = make_booking_executor(_ctx(repo))

    data, err = await _call(execute, "save_service_selection", service="haircut")
    assert err is False                                     # NOT an error → no retry
    assert data["unsupported_request"] is True
    assert data["active_booking"] is True
    assert data["preserved_service"] == "Carpet Cleaning"
    assert data["next_missing_field"] == "pickup_address"
    assert "service_items" not in data["workflow"]["missing_fields"]
    assert repo.row["service_id"] == "CARPET_CLEANING"            # booking intact
    assert repo.start_calls == 0                            # no restart


async def test_haircut_with_no_active_order_declines_and_creates_no_order():
    repo = FakeOrdersRepo(None)                             # no draft at all
    execute = make_booking_executor(_ctx(repo))
    data, err = await _call(execute, "save_service_selection",
                            service="Do you provide haircuts?")
    assert err is False
    assert data["unsupported_request"] is True
    assert data["active_booking"] is False
    assert data["preserved_service"] is None
    assert data["supported_categories"]                     # mentions what we DO offer
    assert repo.row is None and repo.start_calls == 0       # nothing created


# --- null / empty extraction can't erase a saved service -------------------
async def test_empty_service_value_does_not_erase_saved_service():
    repo = FakeOrdersRepo(_carpet_row())
    execute = make_booking_executor(_ctx(repo))
    data, err = await _call(execute, "save_service_selection", service="")
    assert err is False                                     # handled, not an error
    assert repo.row["service_id"] == "CARPET_CLEANING"            # untouched


# --- never re-ask a saved service ------------------------------------------
async def test_same_service_is_a_noop_not_a_reask():
    repo = FakeOrdersRepo(_carpet_row())
    execute = make_booking_executor(_ctx(repo))
    data, err = await _call(execute, "save_service_selection", service="carpet cleaning")
    assert err is False
    assert data.get("already_selected") is True
    assert repo.row["service_id"] == "CARPET_CLEANING"


# --- explicit service edit keeps the rest of the booking -------------------
async def test_service_edit_updates_service_and_keeps_other_fields():
    repo = FakeOrdersRepo({
        "id": "order-uuid-x", "order_id": "LK-2026-000777", "conversation_id": "conv-x",
        "status": order_store.DRAFT, "conversation_state": bf.WAITING_FOR_PICKUP_SLOT,
        "service_id": "WASH_FOLD", "service": "Wash & Fold",
        "service_name_snapshot": "Wash & Fold", "line_items": [],
        "customer_name": "Sara", "pickup_date": _dt.date(2026, 7, 26),
        "pickup_slot": "9am – 12pm",
    })
    execute = make_booking_executor(_ctx(repo))
    data, err = await _call(execute, "save_service_selection", service="clean & press")
    assert err is False and data.get("changed_service") is True
    assert repo.row["service_id"] == "CLEAN_PRESS"          # service changed
    assert repo.row["customer_name"] == "Sara"             # everything else kept
    assert repo.row["pickup_date"] == _dt.date(2026, 7, 26)
    assert repo.row["pickup_slot"] == "9am – 12pm"


# --- additional service: adding an item keeps the primary service ----------
async def test_adding_an_item_preserves_the_saved_service():
    # Find a Clean & Press item that resolves unambiguously (catalogue-driven,
    # so the test isn't brittle to catalogue edits).
    item_name = None
    for it in catalogue.items_for_category("CLEAN_PRESS"):
        if it.get("requires_measurement"):
            continue
        code, reason = bf.resolve_item(bf.Inbound(text=it["canonical_name"]), None, "CLEAN_PRESS")
        if reason == "ok" and code == it["item_code"]:
            item_name = it["canonical_name"]
            break
    if not item_name:
        pytest.skip("no unambiguous Clean & Press item in the catalogue")

    repo = FakeOrdersRepo({
        "id": "order-uuid-x", "order_id": "LK-2026-000777", "conversation_id": "conv-x",
        "status": order_store.DRAFT, "conversation_state": bf.WAITING_FOR_ITEM,
        "service_id": "CLEAN_PRESS", "service": "Clean & Press",
        "service_name_snapshot": "Clean & Press", "line_items": [],
    })
    execute = make_booking_executor(_ctx(repo))
    data, err = await _call(execute, "save_order_item", item=item_name, quantity=2)
    assert err is False and data["saved"] is True
    assert repo.row["service_id"] == "CLEAN_PRESS"          # primary service intact
    assert repo.row["line_items"]                            # the item was added


# --- specialty request routes to a human specialist, not an invented price ---
async def test_villa_cleaning_routes_to_specialist_without_saving_service():
    # A route-to-specialist category (villa/home cleaning) is handed to a
    # specialist rather than quoted, so no order is saved and no price invented.
    # (Wedding dress used to exercise this path; it is now quoted From AED 150.)
    repo = FakeOrdersRepo(None)
    execute = make_booking_executor(_ctx(repo))
    data, err = await _call(execute, "save_service_selection",
                            service="I need a villa deep cleaning")
    assert err is False and data.get("route_to_specialist") is True
    assert data.get("routing_category") == "HOME_CLEANING"
    assert repo.row is None and repo.start_calls == 0       # no order, no invented price


# --- ambiguous request asks one clarification ------------------------------
async def test_ambiguous_ironing_asks_clarification_not_a_guess():
    repo = FakeOrdersRepo(None)
    execute = make_booking_executor(_ctx(repo))
    _data, err = await _call(execute, "save_service_selection", service="ironing")
    assert err is True                                      # a clarify prompt, not a save
    assert repo.row is None                                 # nothing guessed/saved


# --- a bare repair asks ONE clarification, never rejects (spec §2) ----------
async def test_bare_repair_asks_clarification_not_rejected():
    repo = FakeOrdersRepo(None)
    execute = make_booking_executor(_ctx(repo))
    data, err = await _call(execute, "save_service_selection", service="can you repair this?")
    # Not a tool error and NOT an "unsupported" decline — a soft clarification.
    assert err is False
    assert data.get("needs_clarification") is True
    assert data.get("unsupported_request") is not True
    assert repo.row is None                                 # nothing saved yet


# --- a garment repair is accepted as an alteration, not refused (spec §2) ----
async def test_garment_repair_saved_as_alteration():
    repo = FakeOrdersRepo(None)
    execute = make_booking_executor(_ctx(repo))
    data, err = await _call(execute, "save_service_selection",
                            service="can you repair the zip on my jeans")
    assert err is False and data.get("saved") is True
    assert data.get("category_code") == "ALTERATIONS"
