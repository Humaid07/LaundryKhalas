"""Item-collection booking-flow tests (the new step-2/3 of the FSM).

Hermetic: the FSM is driven directly with a fixed ``today`` and injected slots.
Covers category -> (sub-category) -> item -> quantity/measure -> more/done, the
VAT-aware quote in the confirmation summary, starting-price safety, and the
snapshot-immutability + separate-state guarantees (task spec §14 tests 8-12/
17-24).
"""
from __future__ import annotations

import asyncio
import copy
import datetime as _dt

from services import booking_flow as bf
from services import catalogue, pricing
from services.booking_flow import Booking, Inbound

TODAY = _dt.date(2026, 7, 22)
_SLOTS = [{"slot_id": "morning_08_11", "label": "8–11 AM",
           "start_time": _dt.time(8), "end_time": _dt.time(11)}]


async def _slots(*_a, **_k):
    return list(_SLOTS)


def advance(b, inbound):
    return asyncio.run(bf.advance(b, inbound, today=TODAY, available_slots=_slots))


def _apply(booking: Booking, reply) -> Booking:
    """Thread a reply's updates back into the booking (what the webhook/DB do),
    so an end-to-end flow can be driven turn by turn."""
    data = dict(booking.__dict__)
    for k, v in (reply.updates or {}).items():
        if k in data and not k.startswith("_"):
            data[k] = v
    data["conversation_state"] = reply.state
    return Booking(**data)


# --- End-to-end: category -> sub-category -> item -> quantity -> done ---------
def test_full_item_collection_reaches_name_with_priced_summary():
    b = Booking(conversation_state=bf.WAITING_FOR_SERVICE)
    # 1) category
    r = advance(b, Inbound(selection_id="service:CLEAN_PRESS"))
    assert r.state == bf.WAITING_FOR_SUBCATEGORY
    b = _apply(b, r)
    # 2) sub-category
    r = advance(b, Inbound(selection_id="sub:CLEAN_PRESS_EVERYDAY"))
    assert r.state == bf.WAITING_FOR_ITEM
    b = _apply(b, r)
    # 3) item
    r = advance(b, Inbound(selection_id="item:CLEAN_PRESS_SHIRT"))
    assert r.state == bf.WAITING_FOR_ITEM_QUANTITY
    b = _apply(b, r)
    assert b.pending_item_code == "CLEAN_PRESS_SHIRT"
    # 4) quantity
    r = advance(b, Inbound(text="3"))
    assert r.state == bf.WAITING_FOR_MORE_ITEMS
    assert r.updates["line_items"][0]["item_code"] == "CLEAN_PRESS_SHIRT"
    assert r.updates["line_items"][0]["line_total"] == 27.0
    assert r.updates["subtotal_amount"] == 27.0
    assert r.updates["vat_amount"] == 1.35
    assert r.updates["estimated_total"] == 28.35
    assert r.updates["pricing_is_estimated"] is False
    b = _apply(b, r)
    # 5) that's all -> name
    r = advance(b, Inbound(selection_id="items_done"))
    assert r.state == bf.WAITING_FOR_NAME
    b = _apply(b, r)
    b = Booking(**{**b.__dict__, "customer_name": "Sara",
                   "pickup_date": TODAY, "pickup_slot_label": "8–11 AM",
                   "pickup_address": "Marina Heights", "pickup_instruction_text": None,
                   "conversation_state": bf.WAITING_FOR_CONFIRMATION})
    summary = bf._summary_text(b)
    assert "3 × Shirt × AED 9 = AED 27" in summary
    assert "VAT (5%): AED 1.35" in summary
    assert "AED 28.35" in summary
    assert "Prices may vary" in summary


def test_inline_quantity_skips_the_quantity_question():
    b = Booking(conversation_state=bf.WAITING_FOR_ITEM, service_id="CLEAN_PRESS",
                browse_service_code="CLEAN_PRESS_EVERYDAY")
    r = advance(b, Inbound(text="3 shirts"))
    assert r.state == bf.WAITING_FOR_MORE_ITEMS         # quantity read inline
    assert r.updates["subtotal_amount"] == 27.0


def test_add_multiple_items_accumulates():
    b = Booking(conversation_state=bf.WAITING_FOR_MORE_ITEMS, service_id="CLEAN_PRESS",
                browse_service_code="CLEAN_PRESS_EVERYDAY",
                line_items=[{"item_code": "CLEAN_PRESS_SHIRT", "quantity": 3, "measure": None}])
    # "add another" -> back to the sub-category list (Clean & Press has sub-cats)
    r = advance(b, Inbound(selection_id="add_item"))
    assert r.state == bf.WAITING_FOR_SUBCATEGORY
    # typing a second item directly also works
    r2 = advance(b, Inbound(text="2 trousers"))
    assert r2.state == bf.WAITING_FOR_MORE_ITEMS
    codes = [li["item_code"] for li in r2.updates["line_items"]]
    assert codes == ["CLEAN_PRESS_SHIRT", "CLEAN_PRESS_TROUSERS"]
    assert r2.updates["subtotal_amount"] == 49.0        # 27 + 22
    assert r2.updates["vat_amount"] == 2.45
    assert r2.updates["estimated_total"] == 51.45


# --- Wash & Fold (single sub-category -> straight to item/bag list) ----------
def test_wash_fold_goes_straight_to_bag_selection():
    r = advance(Booking(conversation_state=bf.WAITING_FOR_SERVICE),
                Inbound(selection_id="service:WASH_FOLD"))
    assert r.state == bf.WAITING_FOR_ITEM              # no sub-category step
    assert any(o.id == "item:WASH_FOLD_6KG" for o in r.interactive.options)


def test_wash_fold_6kg_bag_prices_at_60():
    b = Booking(conversation_state=bf.WAITING_FOR_ITEM, service_id="WASH_FOLD",
                browse_service_code="WASH_FOLD_BAGS")
    r = advance(b, Inbound(selection_id="item:WASH_FOLD_6KG"))
    assert r.state == bf.WAITING_FOR_ITEM_QUANTITY
    b = _apply(b, r)
    r2 = advance(b, Inbound(text="1"))
    assert r2.updates["subtotal_amount"] == 60.0
    assert r2.updates["vat_amount"] == 3.0


# --- Per-sqm item asks for a measurement, prices as an estimate --------------
def test_curtain_asks_for_sqm_and_prices_as_estimate():
    b = Booking(conversation_state=bf.WAITING_FOR_ITEM, service_id="HOME_CARE",
                browse_service_code="HOME_CARE_SOFA_CURTAINS")
    r = advance(b, Inbound(selection_id="item:HOME_CARE_CURTAIN_SQM"))
    assert r.state == bf.WAITING_FOR_MEASURE
    b = _apply(b, r)
    r2 = advance(b, Inbound(text="4"))
    line = r2.updates["line_items"][0]
    assert line["line_kind"] == "estimate"
    assert line["line_total"] == 80.0                  # 4 sqm × 20
    assert r2.updates["pricing_is_estimated"] is True


# --- Starting-price item is never a guaranteed total in the summary ----------
def test_shoe_starting_price_never_a_total_in_summary():
    b = Booking(conversation_state=bf.WAITING_FOR_ITEM_QUANTITY, service_id="SHOE_CARE",
                browse_service_code="SHOE_CARE_ALL", pending_item_code="SHOE_CARE_SPORTS_SNEAKERS")
    r = advance(b, Inbound(text="2"))
    assert r.updates["subtotal_amount"] == 0.0         # 2 × 50 is NOT charged
    assert r.updates["pricing_is_estimated"] is True
    b = Booking(**{**b.__dict__, "line_items": r.updates["line_items"],
                   "customer_name": "Sara", "conversation_state": bf.WAITING_FOR_CONFIRMATION})
    summary = bf._summary_text(b)
    assert "from aed 50" in summary.lower()
    assert "inspection" in summary.lower()


# --- Required test 23: a confirmed snapshot is immutable across catalogue edits
def test_23_confirmed_snapshot_unchanged_after_catalogue_update(monkeypatch):
    q = pricing.calculate_estimate([{"item_code": "CLEAN_PRESS_SHIRT", "quantity": 3}])
    snapshot = q.to_dict()["lines"]
    assert snapshot[0]["line_total"] == 27.0

    # reprice the shirt in the catalogue
    catalogue.reload_catalogue()
    patched = copy.deepcopy(catalogue._raw())
    for cat in patched["categories"]:
        for svc in cat["services"]:
            for it in svc["items"]:
                if it["code"] == "CLEAN_PRESS_SHIRT":
                    it["current_price"] = 99
    monkeypatch.setattr(catalogue, "_raw", lambda: patched)
    catalogue._index.cache_clear()
    try:
        assert catalogue.item_by_code("CLEAN_PRESS_SHIRT")["current_price"] == 99
        # the frozen snapshot is stored data — it does NOT re-price
        assert snapshot[0]["line_total"] == 27.0
        assert snapshot[0]["unit_price"] == 9
        from db.repositories import orders_repo
        row = {"id": "x", "order_id": "LK-2026-000001", "status": "pickup_scheduled",
               "line_items": snapshot, "subtotal_amount": 27.0, "vat_amount": 1.35,
               "estimated_total": 28.35, "amount": 28.35, "pricing_is_estimated": False,
               "vat_rate": 0.05, "catalogue_category_name": "Clean & Press"}
        read = orders_repo.to_read(row)
        assert read["line_items"][0]["line_total"] == 27.0
        assert read["pricing"]["estimated_total_including_vat"] == 28.35
    finally:
        catalogue._index.cache_clear()
        catalogue.reload_catalogue()


# --- Required test 24: two numbers share the catalogue but keep separate state
def test_24_two_numbers_same_catalogue_separate_order_state():
    a = advance(Booking(conversation_state=bf.WAITING_FOR_ITEM_QUANTITY, service_id="CLEAN_PRESS",
                        browse_service_code="CLEAN_PRESS_EVERYDAY",
                        pending_item_code="CLEAN_PRESS_SHIRT"), Inbound(text="3"))
    b = advance(Booking(conversation_state=bf.WAITING_FOR_ITEM_QUANTITY, service_id="CLEAN_PRESS",
                        browse_service_code="CLEAN_PRESS_EVERYDAY",
                        pending_item_code="CLEAN_PRESS_TROUSERS"), Inbound(text="2"))
    assert a.updates["line_items"][0]["item_code"] == "CLEAN_PRESS_SHIRT"
    assert a.updates["subtotal_amount"] == 27.0
    assert b.updates["line_items"][0]["item_code"] == "CLEAN_PRESS_TROUSERS"
    assert b.updates["subtotal_amount"] == 22.0
    # both priced from the SAME catalogue values
    assert catalogue.item_by_code("CLEAN_PRESS_SHIRT")["current_price"] == 9
    assert catalogue.item_by_code("CLEAN_PRESS_TROUSERS")["current_price"] == 11


# --- Ambiguous "ironing" asks Clean & Press vs Press Only (test 20 at FSM) ----
def test_bare_ironing_prompts_clean_press_vs_press_only():
    r = advance(Booking(conversation_state=bf.WAITING_FOR_SERVICE),
                Inbound(text="i need ironing"))
    assert r.state == bf.WAITING_FOR_SERVICE
    ids = [o.id for o in r.interactive.options]
    assert ids == ["service:CLEAN_PRESS", "service:PRESS_ONLY"]
