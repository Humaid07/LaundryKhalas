"""Pure builder for the admin-triggered Stripe payment link (spec
2026-08-06-stripe-payment-link-wiring). No I/O — the eligibility guards + the
order-row -> InvoiceRequest mapping, fully offline.
"""
from __future__ import annotations

import pytest

from services.payments.invoicing import (
    build_invoice_request,
    ensure_invoice_for_order,
    render_payment_message,
)


def _order(**over) -> dict:
    base = {
        "order_id": "LK-AE-1024",
        "status": "active",
        "payment_preference": "STRIPE",
        "amount": 69.0,
        "currency": "AED",
        "customer_name": "Aisha",
        "customer_phone": "+971500000000",
        "city": "Dubai",
        "pickup_area": "Marina",
        "service_type": "Wash & Fold",
        "stripe_invoice_id": None,
    }
    base.update(over)
    return base


# --- happy path -------------------------------------------------------------
def test_eligible_order_builds_request():
    req, reason = build_invoice_request(_order())
    assert reason is None
    assert req is not None
    assert req.order_id == "LK-AE-1024"
    assert req.idempotency_key == "LK-AE-1024"
    assert req.currency == "aed"
    assert req.total_minor == 6900          # 69.00 -> minor units
    assert len(req.line_items) == 1
    assert req.line_items[0].amount_minor == 6900
    assert req.customer.name == "Aisha"
    assert req.customer.phone == "+971500000000"
    assert req.customer.country == "AE"      # from LK-AE- prefix (Stripe Tax)


def test_amount_minor_conversion():
    assert build_invoice_request(_order(amount=12.34))[0].total_minor == 1234
    assert build_invoice_request(_order(amount=100))[0].total_minor == 10000
    assert build_invoice_request(_order(amount=69.5))[0].total_minor == 6950


def test_country_from_qatar_prefix():
    req, _ = build_invoice_request(_order(order_id="LK-QA-2001"))
    assert req.customer.country == "QA"


def test_country_none_for_unknown_prefix():
    req, _ = build_invoice_request(_order(order_id="XX-1"))
    assert req.customer.country is None


def test_automatic_tax_flag_passed_through():
    req, _ = build_invoice_request(_order(), automatic_tax=True)
    assert req.automatic_tax is True
    req2, _ = build_invoice_request(_order())
    assert req2.automatic_tax is False


# --- eligibility guards -----------------------------------------------------
@pytest.mark.parametrize("status", ["draft", "cancelled", "abandoned", "completed"])
def test_ineligible_status_returns_reason(status):
    req, reason = build_invoice_request(_order(status=status))
    assert req is None
    assert reason  # a human-readable reason is always given


def test_non_stripe_preference_rejected():
    req, reason = build_invoice_request(_order(payment_preference="CASH_ON_DELIVERY"))
    assert req is None
    assert "stripe" in reason.lower()


def test_missing_amount_rejected():
    for amt in (None, 0, 0.0):
        req, reason = build_invoice_request(_order(amount=amt))
        assert req is None
        assert "amount" in reason.lower()


def test_already_invoiced_is_skipped():
    req, reason = build_invoice_request(_order(stripe_invoice_id="in_test_existing"))
    assert req is None
    assert "already" in reason.lower() or "exists" in reason.lower()


# --- ensure_invoice_for_order orchestration (mock gateway; STRIPE_MODE=mock) --
async def test_ensure_invoice_creates_via_gateway_and_persists(monkeypatch):
    calls = []

    async def _record_execute(sql, *params):
        calls.append((sql, params))

    import db.database as dbmod
    monkeypatch.setattr(dbmod, "execute", _record_execute)

    result = await ensure_invoice_for_order(_order(id="uuid-1"))
    assert result is not None
    assert result.is_mock is True                       # mock gateway in the test suite
    assert result.hosted_invoice_url.startswith("https://")
    assert result.amount_due_minor == 6900
    # persisted: the orders UPDATE + an order_events insert
    assert any("update orders set stripe" in sql for sql, _ in calls)
    assert any("payment_link_created" in sql for sql, _ in calls)


async def test_ensure_invoice_none_when_ineligible(monkeypatch):
    async def _boom(*a, **k):
        raise AssertionError("must not persist for an ineligible order")

    import db.database as dbmod
    monkeypatch.setattr(dbmod, "execute", _boom)

    assert await ensure_invoice_for_order(_order(status="draft")) is None
    assert await ensure_invoice_for_order(_order(payment_preference="CASH_ON_DELIVERY")) is None
    assert await ensure_invoice_for_order(_order(stripe_invoice_id="in_x")) is None


# --- pending-approval customer message (pure) -------------------------------
def test_render_payment_message_contains_link_amount_order():
    msg = render_payment_message(
        name="Aisha", order_id="LK-AE-1024", amount_major=69.0, currency="aed",
        hosted_url="https://invoice.stripe.com/i/abc")
    assert "https://invoice.stripe.com/i/abc" in msg
    assert "LK-AE-1024" in msg
    assert "69.00" in msg
    assert "AED" in msg
    # reply-style compliant: no emoji / exclamation
    assert "!" not in msg


def test_render_payment_message_handles_missing_name():
    msg = render_payment_message(
        name="", order_id="LK-AE-1024", amount_major=10.0, currency="aed",
        hosted_url="https://x")
    assert msg  # still renders a sensible greeting


# --- endpoint registration + Supabase guard (sqlite hermetic suite) ---------
async def test_payment_link_endpoints_require_supabase(client):
    # The hermetic suite runs sqlite mode, so these live-only endpoints must
    # 400 (and be registered/ops-gated), never 404/500.
    r = await client.post("/api/orders/LK-AE-1024/payment-link")
    assert r.status_code == 400
    assert "supabase" in r.json()["detail"].lower()
    r2 = await client.post(
        "/api/orders/LK-AE-1024/payment-link/approve", json={"message_id": "m1"})
    assert r2.status_code == 400
