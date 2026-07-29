"""Stage 5 — privacy firewall (CLAUDE.md §7 / spec §7), adversarial.

Feeds PII (customer phone, email, full address) into every outward/derived surface
and asserts it NEVER appears in:
  * facility / driver-facing notification text;
  * the model-facing structured state block;
  * the get_customer_record tool output.
Plus unit coverage of services.privacy.mask_pii.
"""
from __future__ import annotations

import datetime as _dt
import json

from agents.whatsapp_agent.booking_tools import (
    BookingContext,
    make_booking_executor,
    workflow_state_block,
)
from services import facility_notifications, order_store, privacy
from services import booking_flow as bf

# A distinctive PII payload we can grep for in any output.
PHONE = "+971501234567"
EMAIL = "sara.customer@example.com"
FULL_ADDRESS = "Villa 12, Street 7, Al Barsha 2, near the mosque"
PII_STRINGS = [PHONE, "971501234567", EMAIL, "Villa 12", "Street 7", "near the mosque"]


def _assert_no_pii(blob: str):
    for needle in PII_STRINGS:
        assert needle not in blob, f"PII leaked: {needle!r} in {blob!r}"


# --------------------------------------------------------------------------
# mask_pii unit
# --------------------------------------------------------------------------
def test_mask_pii_masks_phone_and_email_keeps_short_tokens():
    masked = privacy.mask_pii(f"Call {PHONE} or email {EMAIL} about order LK-1023 at 7pm")
    assert PHONE not in masked and EMAIL not in masked
    assert "[phone hidden]" in masked and "[email hidden]" in masked
    assert "LK-1023" in masked and "7pm" in masked   # short tokens survive


# --------------------------------------------------------------------------
# Facility / driver-facing notifications
# --------------------------------------------------------------------------
def test_facility_new_order_preview_has_no_customer_pii():
    order_read = {
        "order_id": "LK-2026-000123", "service": "Wash & Fold", "area": "Al Barsha",
        # Adversarial: PII present on the record must NOT reach the facility text.
        "customer_phone": PHONE, "customer_email": EMAIL, "pickup_address": FULL_ADDRESS,
    }
    _assert_no_pii(facility_notifications._new_order_preview(order_read))


def test_facility_status_preview_has_no_customer_pii():
    order_read = {
        "order_id": "LK-2026-000123", "turnaround_text": "24 hours",
        "customer_phone": PHONE, "customer_email": EMAIL, "pickup_address": FULL_ADDRESS,
    }
    _assert_no_pii(facility_notifications._status_preview(order_read, "in_cleaning"))


# --------------------------------------------------------------------------
# Model-facing structured state block
# --------------------------------------------------------------------------
def test_state_block_omits_full_address_and_phone():
    row = {
        "order_id": "LK-2026-000123", "conversation_state": bf.WAITING_FOR_CONFIRMATION,
        "customer_name": "Sara", "service_name_snapshot": "Wash & Fold",
        "line_items": [{"item_code": "WASH_FOLD_6KG", "name": "Wash & Fold", "quantity": 1,
                        "line_kind": "estimate"}],
        "pickup_date": _dt.date(2026, 7, 30), "pickup_slot": "5:00 PM–8:00 PM",
        "pickup_address": f"{FULL_ADDRESS} {PHONE}", "pickup_area": "Al Barsha",
    }
    block = workflow_state_block(row)
    # Only a boolean + the area are exposed — never the full address / phone.
    assert block["order"]["pickup_address_present"] is True
    assert block["order"]["pickup_area"] == "Al Barsha"
    _assert_no_pii(json.dumps(block))


# --------------------------------------------------------------------------
# get_customer_record tool
# --------------------------------------------------------------------------
class _Repo:
    def __init__(self):
        self.row = {"id": "o1", "order_id": "LK-1", "conversation_id": "c1",
                    "status": order_store.DRAFT, "conversation_state": bf.WAITING_FOR_SERVICE}

    async def get_active_draft(self, conversation_id):
        return self.row if self.row["status"] == order_store.DRAFT else None

    async def apply_booking_updates(self, order_uuid, updates, state):
        return self.row

    async def get_latest_for_conversation(self, conversation_id):
        return self.row


async def _slots(*a, **k):
    return []


async def test_get_customer_record_returns_no_phone_email_or_full_address():
    repo = _Repo()
    ctx = BookingContext(
        conversation_id="c1", order_uuid="o1", repo=repo, today=_dt.date(2026, 7, 29),
        available_slots=_slots, market="AE", verified_name="Sara",
        customer={"id": "cust-1", "area": "Al Barsha", "city": "Dubai", "market": "AE",
                  "phone_e164": PHONE, "email": EMAIL, "address": FULL_ADDRESS,
                  "preferred_language": "en"})
    text, err = await make_booking_executor(ctx)("get_customer_record", {})
    assert err is False
    data = json.loads(text)
    assert data["confirmed_name"] == "Sara"
    assert data["area"] == "Al Barsha"
    _assert_no_pii(text)
