"""QA (Qatar / QAR) market pricing (spec §8), sourced from the QA website overlay.

Asserts: QAR prices are used for QA, the AE baseline is unchanged, an item with no
QA price becomes inspection-only (never quoted in AED), and the currency never mixes.
"""
from __future__ import annotations

import datetime as _dt
import json

import pytest

from agents.whatsapp_agent import llm_tools
from agents.whatsapp_agent.booking_tools import BookingContext, make_booking_executor
from services import booking_flow as bf
from services import catalogue, market, order_store, pricing


@pytest.fixture(autouse=True)
def _fresh():
    catalogue.reload_catalogue()
    market.reload_markets()
    yield
    catalogue.reload_catalogue()
    market.reload_markets()


# --------------------------------------------------------------------------
# Catalogue overlay
# --------------------------------------------------------------------------
def test_qa_market_is_configured_with_qar():
    assert market.get_market("QA").pricing_configured is True
    assert catalogue.has_market_pricing("QA") is True
    assert catalogue.market_currency("QA") == "QAR"
    assert catalogue.market_currency("AE") == "AED"


def test_qa_wash_fold_prices_match_ruleset_2026_08_05():
    prices = catalogue.market_prices("QA")
    # Ruleset 2026_08_05: QAR 12 additional-kg (was 10.95), QAR 90 for the 12 kg bag.
    assert prices["WASH_FOLD_ADDITIONAL_KG"] == 12
    assert prices["WASH_FOLD_12KG"] == 90
    assert prices["CLEAN_PRESS_SHIRT"] == 9


# --------------------------------------------------------------------------
# Quote engine
# --------------------------------------------------------------------------
def test_qa_quote_uses_qar_prices_and_currency():
    q = pricing.calculate_estimate(
        [{"item_code": "WASH_FOLD_6KG", "quantity": 1},
         {"item_code": "WASH_FOLD_ADDITIONAL_KG", "quantity": 1, "measure": 4}],
        market="QA")
    assert q.currency == "QAR"
    assert q.customer_total == 108.0           # 60 + 4×12 (ruleset 2026_08_05)
    assert all("QAR" in ln for ln in pricing.format_quote_lines(q))


def test_ae_baseline_unchanged():
    q = pricing.calculate_estimate([{"item_code": "WASH_FOLD_6KG", "quantity": 1},
                                    {"item_code": "WASH_FOLD_ADDITIONAL_KG", "quantity": 1, "measure": 4}])
    assert q.currency == "AED"
    assert q.customer_total == 108.0           # 60 + 4×12 (ruleset 2026_08_05)


def test_qa_unpriced_item_is_inspection_not_aed():
    q = pricing.calculate_estimate([{"item_code": "HOME_CARE_DUVET", "quantity": 1}], market="QA")
    assert q.customer_total == 0.0             # excluded from payable total
    assert q.has_pending_inspection is True
    assert "42" not in " ".join(pricing.format_quote_lines(q))   # never the AED number


# --------------------------------------------------------------------------
# lookup_item_price grounding tool
# --------------------------------------------------------------------------
async def test_lookup_item_price_qar():
    text, err = await llm_tools.execute_tool("lookup_item_price", {"query": "cardigan"}, market="QA")
    assert err is False
    data = json.loads(text)
    assert data["match"] == "ok"
    assert data["currency"] == "QAR"
    assert "QAR 18" in data["price_label"]


async def test_lookup_item_price_aed_default():
    text, _ = await llm_tools.execute_tool("lookup_item_price", {"query": "cardigan"})
    data = json.loads(text)
    assert data["currency"] == "AED"
    assert "AED 18" in data["price_label"]


# --------------------------------------------------------------------------
# End-to-end through the booking tool (order summary in QAR)
# --------------------------------------------------------------------------
class _Repo:
    def __init__(self):
        self.row = {"id": "o1", "order_id": "LK-QA-1", "conversation_id": "c1",
                    "status": order_store.DRAFT, "conversation_state": bf.WAITING_FOR_SERVICE,
                    "line_items": [{"item_code": "CLEAN_PRESS_SHIRT", "quantity": 5}],
                    "catalogue_category_code": "CLEAN_PRESS"}

    async def get_active_draft(self, conversation_id):
        return self.row if self.row["status"] == order_store.DRAFT else None

    async def apply_booking_updates(self, order_uuid, updates, state):
        self.row.update(updates or {})
        return self.row

    async def get_latest_for_conversation(self, conversation_id):
        return self.row


async def _slots(*a, **k):
    return []


async def test_order_summary_in_qar_for_qatar_customer():
    repo = _Repo()
    ctx = BookingContext(conversation_id="c1", order_uuid="o1", repo=repo,
                         today=_dt.date(2026, 7, 29), available_slots=_slots, market="QA")
    text, err = await make_booking_executor(ctx)("get_order_summary", {})
    assert err is False
    data = json.loads(text)
    assert data["final_price_aed"] == 45.0     # 5 × QAR 9 (field name is legacy)
    assert all("QAR" in ln for ln in data["summary_lines"])
    # QA delivery: 45 >= 30 → free (ruleset 2026_08_05 minimum QAR 30)
    assert data["delivery_free"] is True and data["delivery_fee_aed"] == 0.0
