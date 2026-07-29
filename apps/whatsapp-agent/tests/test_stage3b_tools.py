"""Stage 3b — min-order delivery fee in the summary (§2.3) and the Express
same-day tool (§2.4). Offline against the fake orders repo.
"""
from __future__ import annotations

import datetime as _dt
import json

from agents.whatsapp_agent.booking_tools import BookingContext, make_booking_executor
from services import booking_flow as bf
from services import order_store


class _Repo:
    def __init__(self):
        self.row = {
            "id": "o1", "order_id": "LK-1", "conversation_id": "c1",
            "status": order_store.DRAFT, "conversation_state": bf.WAITING_FOR_SERVICE,
        }

    async def get_active_draft(self, conversation_id):
        return self.row if self.row["status"] == order_store.DRAFT else None

    async def apply_booking_updates(self, order_uuid, updates, state):
        self.row.update({k: v for k, v in (updates or {}).items() if k != "_touch_service_selected_at"})
        self.row["conversation_state"] = state
        return self.row

    async def get_latest_for_conversation(self, conversation_id):
        return self.row


async def _slots(*a, **k):
    return []


def _ctx(repo, now=None):
    return BookingContext(
        conversation_id="c1", order_uuid="o1", repo=repo,
        today=_dt.date(2026, 7, 29), available_slots=_slots, now=now, market="AE")


async def _call(execute, tool, **inp):
    text, is_error = await execute(tool, inp)
    return json.loads(text), is_error


# --------------------------------------------------------------------------
# Min-order delivery fee in the order summary (§2.3)
# --------------------------------------------------------------------------
async def test_summary_charges_flat_fee_below_minimum():
    repo = _Repo()
    repo.row.update({  # 1 shirt @ AED 9 → below the AED 50 minimum
        "line_items": [{"item_code": "CLEAN_PRESS_SHIRT", "quantity": 1}],
        "catalogue_category_code": "CLEAN_PRESS", "catalogue_category_name": "Clean & Press",
    })
    data, err = await _call(make_booking_executor(_ctx(repo)), "get_order_summary")
    assert err is False
    assert data["delivery_free"] is False
    assert data["delivery_fee_aed"] == 8.0
    assert data["order_grand_total_aed"] == data["final_price_aed"] + 8.0


async def test_summary_free_delivery_at_or_above_minimum():
    repo = _Repo()
    repo.row.update({  # 8 shirts @ AED 9 = 72 → free
        "line_items": [{"item_code": "CLEAN_PRESS_SHIRT", "quantity": 8}],
        "catalogue_category_code": "CLEAN_PRESS", "catalogue_category_name": "Clean & Press",
    })
    data, _ = await _call(make_booking_executor(_ctx(repo)), "get_order_summary")
    assert data["delivery_free"] is True
    assert data["delivery_fee_aed"] == 0.0
    assert data["order_grand_total_aed"] == data["final_price_aed"]


# --------------------------------------------------------------------------
# Express same-day tool (§2.4)
# --------------------------------------------------------------------------
async def test_express_before_cutoff_offers_surcharged_total():
    repo = _Repo()
    repo.row.update({
        "line_items": [{"item_code": "WASH_FOLD_6KG", "quantity": 1}],
        "catalogue_category_code": "WASH_FOLD", "catalogue_category_name": "Wash & Fold",
    })
    ctx = _ctx(repo, now=_dt.datetime(2026, 7, 29, 11, 0))
    data, err = await _call(make_booking_executor(ctx), "quote_express")
    assert err is False
    assert data["eligible"] is True
    assert data["requires_facility_check"] is False
    assert data["surcharge_pct"] == 0.5
    assert "express" in data["customer_safe_summary"].lower()


async def test_express_after_cutoff_requires_facility_check_not_rejected():
    repo = _Repo()
    repo.row.update({
        "line_items": [{"item_code": "WASH_FOLD_6KG", "quantity": 1}],
        "catalogue_category_code": "WASH_FOLD", "catalogue_category_name": "Wash & Fold",
    })
    ctx = _ctx(repo, now=_dt.datetime(2026, 7, 29, 16, 30))
    data, _ = await _call(make_booking_executor(ctx), "quote_express")
    assert data["eligible"] is True
    assert data["requires_facility_check"] is True
    assert "facility" in data["customer_safe_summary"].lower()


async def test_express_ineligible_for_mixed_order():
    repo = _Repo()
    repo.row.update({
        "line_items": [{"item_code": "WASH_FOLD_6KG", "quantity": 1},
                       {"item_code": "SHOE_CARE_SPORTS_SNEAKERS", "quantity": 1}],
        "catalogue_category_code": "WASH_FOLD", "catalogue_category_name": "Wash & Fold",
    })
    ctx = _ctx(repo, now=_dt.datetime(2026, 7, 29, 11, 0))
    data, _ = await _call(make_booking_executor(ctx), "quote_express")
    assert data["eligible"] is False
