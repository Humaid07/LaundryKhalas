"""Phase B — the /webhooks/stripe route (mock-mode, offline).

In the hermetic suite STRIPE_MODE=mock, so get_gateway() returns the mock gateway
whose parse_webhook_event just reads the JSON envelope (no signing secret needed).
That lets us drive real Stripe-shaped events through the actual route and assert
the order settles correctly and idempotently.
"""
from __future__ import annotations

import json

import pytest

from db import AsyncSessionLocal
from services import order_store


def _invoice_event(event_type: str, *, order_id="", invoice_id="in_mock_1",
                   amount_paid=8400, currency="aed") -> bytes:
    return json.dumps({
        "id": f"evt_{event_type}",
        "type": event_type,
        "data": {"object": {
            "id": invoice_id,
            "amount_paid": amount_paid,
            "amount_due": amount_paid,
            "currency": currency,
            "hosted_invoice_url": f"https://pay.stripe.test/i/{invoice_id}",
            "metadata": {"order_id": order_id},
        }},
    }).encode()


async def _order_payment(order_id_text: str) -> tuple[str, str | None, int | None]:
    async with AsyncSessionLocal() as db:
        order = await order_store.find_order_by_id(db, order_id_text)
        assert order is not None, f"order {order_id_text} not seeded"
        return order.payment_status, order.stripe_invoice_id, order.amount_paid_minor


async def test_invoice_paid_marks_order_paid(client):
    resp = await client.post(
        "/webhooks/stripe",
        content=_invoice_event("invoice.paid", order_id="LK-AE-1024"),
        headers={"stripe-signature": "mock", "content-type": "application/json"},
    )
    assert resp.status_code == 200
    status, inv, paid = await _order_payment("LK-AE-1024")
    assert status == "paid"
    assert inv == "in_mock_1"
    assert paid == 8400


async def test_invoice_paid_is_idempotent(client):
    body = _invoice_event("invoice.paid", order_id="LK-AE-1025")
    hdr = {"stripe-signature": "mock", "content-type": "application/json"}
    r1 = await client.post("/webhooks/stripe", content=body, headers=hdr)
    r2 = await client.post("/webhooks/stripe", content=body, headers=hdr)
    assert r1.status_code == 200 and r2.status_code == 200
    status, _, _ = await _order_payment("LK-AE-1025")
    assert status == "paid"


async def test_payment_failed_marks_order_failed(client):
    resp = await client.post(
        "/webhooks/stripe",
        content=_invoice_event("invoice.payment_failed", order_id="LK-AE-1026"),
        headers={"stripe-signature": "mock", "content-type": "application/json"},
    )
    assert resp.status_code == 200
    status, _, _ = await _order_payment("LK-AE-1026")
    assert status == "failed"


async def test_unhandled_event_type_is_acknowledged_without_change(client):
    resp = await client.post(
        "/webhooks/stripe",
        content=_invoice_event("customer.updated", order_id="LK-AE-1027"),
        headers={"stripe-signature": "mock", "content-type": "application/json"},
    )
    assert resp.status_code == 200
    status, _, _ = await _order_payment("LK-AE-1027")
    assert status == "unpaid"  # untouched


async def test_garbage_payload_returns_400(client):
    resp = await client.post(
        "/webhooks/stripe",
        content=b"not json at all",
        headers={"stripe-signature": "mock", "content-type": "application/json"},
    )
    assert resp.status_code == 400


async def test_event_for_unknown_order_is_acknowledged(client):
    # Stripe retries until it gets a 2xx; an event we can't match to an order must
    # still be acknowledged (200) so Stripe stops retrying — not 500.
    resp = await client.post(
        "/webhooks/stripe",
        content=_invoice_event("invoice.paid", order_id="LK-AE-9999", invoice_id="in_mock_x"),
        headers={"stripe-signature": "mock", "content-type": "application/json"},
    )
    assert resp.status_code == 200


async def test_order_matched_by_invoice_id_when_no_metadata(client):
    # Pre-link an invoice id on an order, then send an event with NO metadata.order_id.
    async with AsyncSessionLocal() as db:
        order = await order_store.find_order_by_id(db, "LK-AE-1024")
        order.stripe_invoice_id = "in_mock_linked"
        await db.commit()
    resp = await client.post(
        "/webhooks/stripe",
        content=_invoice_event("invoice.paid", order_id="", invoice_id="in_mock_linked"),
        headers={"stripe-signature": "mock", "content-type": "application/json"},
    )
    assert resp.status_code == 200
    status, _, _ = await _order_payment("LK-AE-1024")
    assert status == "paid"
