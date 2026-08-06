"""Area 7 — privacy firewall, facility isolation, finance privacy, fee immutability.

Consolidates the cross-cutting guarantees: the facility payload never leaks
internal financials/PII, every facility repo is scoped by facility_id, finance
shows only the facility fee + payout, the fee comes from an immutable per-order
snapshot (never recomputed), and customer fields honour the share config.
"""
import json

import pytest

from db import database
from db.repositories import (
    facility_order_reviews_repo,
    facility_orders_repo,
    facility_quote_revisions_repo,
    order_photos_repo,
)
from services import facility_order_view as view
from services.facility_handoff import FacilityShareConfig


# ------------------------ full-payload no-leak ---------------------------
def _loaded_order():
    return {
        "id": "u1", "order_id": "LK-AE-1024", "status": "picked_up",
        "service_display_name": "Alterations",
        "line_items": [{"id": "li-1", "name": "Trouser", "quantity": 2}],
        # every one of these MUST be absent from the facility payload:
        "amount": 999.0, "estimated_total": 999.0,
        "laundrykhalas_margin": 250.0, "platform_net": 700.0,
        "stripe_payment_intent": "pi_live_secret", "stripe_hosted_invoice_url": "https://pay/x",
        "internal_routing_score": 0.87, "competing_facility_rate": 33.0,
        "customer_phone": "+971501234567", "customer_email": "a@b.com",
        "pickup_address": "Villa 12, Marina",
    }


def test_full_view_never_leaks_internal_financials_or_pii():
    share = FacilityShareConfig(True, True, True, True)
    payload = view.build_facility_order_view(
        order=_loaded_order(), active_notes=[], notes_all=[], photos=[], issues=[],
        fee_snapshot={"facility_cost": 40, "currency": "AED", "complete": True},
        review=None, share=share, customer=None,
        quote_revisions=[{"id": "r1", "customer_price": 52, "status": "customer_pending"}],
    )
    blob = json.dumps(payload).lower()
    for forbidden in ("margin", "stripe", "platform_net", "routing_score",
                      "competing_facility", "999", "pi_live", "+971501234567", "a@b.com"):
        assert forbidden not in blob, f"leaked: {forbidden}"


# ------------------------- finance is fee-only ---------------------------
def test_finance_exposes_only_fee_and_payout():
    fin = view.build_facility_finance(
        {"facility_cost": 40, "currency": "AED", "complete": True,
         "margin": 20, "customer_amount": 60},  # extra keys must NOT pass through
        {"facility_fee_total": 40, "payout_status": "pending"},
    )
    assert set(fin.keys()) <= {"fee_total", "currency", "per_item", "complete", "payout_status"}
    assert fin["fee_total"] == 40.0
    assert "margin" not in fin and "customer_amount" not in fin


# ---------------- immutable per-order fee snapshot -----------------------
def test_fee_comes_from_snapshot_not_a_live_rate_card():
    # The finance block reads the ORDER's frozen fee, never a (possibly newer)
    # rate card — build_facility_finance takes no rate-card input at all.
    order = {"facility_fee_total": 40, "facility_fee_currency": "AED"}
    fin = view.build_facility_finance(None, order)
    assert fin["fee_total"] == 40.0  # from the immutable order snapshot
    # A different snapshot value flows straight through (no recomputation).
    fin2 = view.build_facility_finance({"facility_cost": 55, "complete": True}, {})
    assert fin2["fee_total"] == 55.0


# --------------------- customer share-config gating ----------------------
def test_customer_fields_omitted_when_share_off():
    off = FacilityShareConfig(False, False, False, False)
    payload = view.build_facility_order_view(
        order=_loaded_order(), active_notes=[], notes_all=[], photos=[], issues=[],
        fee_snapshot=None, review=None, share=off,
        customer={"customer_name": "Aisha", "normalized_contact_number": "+9715"},
    )
    assert "name" not in payload["customer"] and "phone" not in payload["customer"]
    assert "typed_address" not in payload["location"]


# ------------------------- facility isolation ----------------------------
@pytest.mark.parametrize("run", [
    ("photos_get", lambda: order_photos_repo.get("p1", "FAC-A")),
    ("review_latest", lambda: facility_order_reviews_repo.latest_for_order("FAC-A", "o1")),
    ("order_get", lambda: facility_orders_repo.get("FAC-A", "LK-1")),
    ("quote_get", lambda: facility_quote_revisions_repo.get("r1", facility_id="FAC-A")),
])
async def test_every_facility_read_is_scoped_by_facility_id(run, monkeypatch):
    captured = {}

    async def fake_fetchrow(sql, *args):
        captured["sql"] = sql
        captured["args"] = args
        return None

    monkeypatch.setattr(database, "fetchrow", fake_fetchrow)
    await run[1]()
    assert "facility_id" in captured["sql"], f"{run[0]} not scoped by facility_id"
    assert "FAC-A" in captured["args"], f"{run[0]} did not bind the principal's facility"


async def test_photo_soft_delete_is_scoped(monkeypatch):
    captured = {}

    async def fake_fetchrow(sql, *args):
        captured["sql"] = sql
        return None

    monkeypatch.setattr(database, "fetchrow", fake_fetchrow)
    await order_photos_repo.soft_delete("p1", "FAC-A")
    assert "facility_id = $2" in captured["sql"]
