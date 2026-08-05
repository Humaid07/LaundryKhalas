"""Phase B — the real StripeProvider, exercised against an injected fake client
(no network). These pin the Stripe best-practices that are easy to get wrong:

  * Invoicing flow: customer → invoice items → invoice → finalize.
  * automatic_tax is sent ONLY when requested (never silently on/off).
  * `payment_method_types` is NEVER passed (dynamic payment methods).
  * idempotency keys on every create so a retry can't double-create.
  * order_id is written to invoice metadata (so the webhook can map back).
  * webhook signature is verified; a bad/absent secret raises ValueError.
"""
from __future__ import annotations

import json

import pytest

from services.payments import base
from services.payments.stripe_provider import StripeProvider


# --- an in-memory fake of stripe.StripeClient().v1 --------------------------
class _Obj:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _Customers:
    def __init__(self):
        self.calls = []

    async def create_async(self, params, options=None):
        self.calls.append({"params": params, "options": options})
        return _Obj(id="cus_test_1")


class _InvoiceItems:
    def __init__(self):
        self.calls = []

    async def create_async(self, params, options=None):
        self.calls.append({"params": params, "options": options})
        return _Obj(id=f"ii_{len(self.calls)}")


class _Invoices:
    def __init__(self):
        self.create_calls = []
        self.finalized = []

    async def create_async(self, params, options=None):
        self.create_calls.append({"params": params, "options": options})
        return _Obj(id="in_test_1")

    async def finalize_invoice_async(self, invoice_id, params=None, options=None):
        self.finalized.append(invoice_id)
        return _Obj(
            id=invoice_id,
            hosted_invoice_url="https://pay.stripe.test/i/in_test_1",
            invoice_pdf="https://pay.stripe.test/i/in_test_1.pdf",
            status="open",
            amount_due=8400,
            currency="aed",
        )


class _V1:
    def __init__(self):
        self.customers = _Customers()
        self.invoice_items = _InvoiceItems()
        self.invoices = _Invoices()


class _FakeClient:
    def __init__(self):
        self.v1 = _V1()


def _provider(client=None, **kw) -> StripeProvider:
    return StripeProvider(
        api_key="sk_test_x",
        api_version="2026-07-29.dahlia",
        default_currency="aed",
        webhook_secret=kw.pop("webhook_secret", "whsec_test"),
        client=client or _FakeClient(),
    )


def _request(**kw) -> base.InvoiceRequest:
    return base.InvoiceRequest(
        customer=base.PaymentCustomer(
            name="Aisha", email="a@example.com", country="AE", city="Dubai"),
        line_items=[
            base.InvoiceLineItem(description="Wash & Fold 6kg", amount_minor=5400),
            base.InvoiceLineItem(description="Express surcharge", amount_minor=1500, quantity=2),
        ],
        currency="aed",
        order_id="LK-AE-2001",
        idempotency_key="LK-AE-2001",
        **kw,
    )


def _all_params(client: _FakeClient) -> list[dict]:
    """Every params dict sent to Stripe this run — used to assert a param is
    NEVER present anywhere in the flow."""
    v1 = client.v1
    out = [c["params"] for c in v1.customers.calls]
    out += [c["params"] for c in v1.invoice_items.calls]
    out += [c["params"] for c in v1.invoices.create_calls]
    return out


async def test_create_invoice_runs_full_invoicing_flow():
    client = _FakeClient()
    result = await _provider(client).create_invoice(_request())

    # customer created with the tax-relevant address
    assert len(client.v1.customers.calls) == 1
    cust = client.v1.customers.calls[0]["params"]
    assert cust["name"] == "Aisha"
    assert cust["address"]["country"] == "AE"

    # invoice created (draft) BEFORE items, so each item can attach to it
    assert len(client.v1.invoices.create_calls) == 1

    # one invoice item per line, amounts in minor units (1500*2 collapsed to total),
    # each EXPLICITLY attached to the draft invoice (else Stripe finalizes an empty
    # $0 invoice — the bug the live sandbox check caught).
    items = client.v1.invoice_items.calls
    assert [i["params"]["amount"] for i in items] == [5400, 3000]
    assert all(i["params"]["currency"] == "aed" for i in items)
    assert all(i["params"]["invoice"] == "in_test_1" for i in items)

    # finalized last
    assert client.v1.invoices.finalized == ["in_test_1"]

    # result carries the hosted pay link + pdf from the finalized invoice
    assert result.provider == "stripe"
    assert result.is_mock is False
    assert result.hosted_invoice_url == "https://pay.stripe.test/i/in_test_1"
    assert result.invoice_pdf_url == "https://pay.stripe.test/i/in_test_1.pdf"
    assert result.amount_due_minor == 8400
    assert result.customer_id == "cus_test_1"


async def test_order_id_written_to_invoice_metadata():
    client = _FakeClient()
    await _provider(client).create_invoice(_request())
    inv = client.v1.invoices.create_calls[0]["params"]
    assert inv["metadata"]["order_id"] == "LK-AE-2001"


async def test_automatic_tax_sent_only_when_requested():
    client = _FakeClient()
    await _provider(client).create_invoice(_request(automatic_tax=True))
    inv = client.v1.invoices.create_calls[0]["params"]
    assert inv["automatic_tax"] == {"enabled": True}


async def test_automatic_tax_absent_when_not_requested():
    client = _FakeClient()
    await _provider(client).create_invoice(_request(automatic_tax=False))
    inv = client.v1.invoices.create_calls[0]["params"]
    assert "automatic_tax" not in inv


async def test_never_passes_payment_method_types_anywhere():
    client = _FakeClient()
    await _provider(client).create_invoice(_request(automatic_tax=True))
    for params in _all_params(client):
        assert "payment_method_types" not in params


async def test_idempotency_key_on_every_create():
    client = _FakeClient()
    await _provider(client).create_invoice(_request())
    # customer + items + invoice create all carry an idempotency key derived from
    # the order id, so a retried turn never creates duplicates.
    assert client.v1.customers.calls[0]["options"]["idempotency_key"]
    for item in client.v1.invoice_items.calls:
        assert item["options"]["idempotency_key"]
    assert client.v1.invoices.create_calls[0]["options"]["idempotency_key"]


async def test_invoice_uses_send_invoice_collection_method():
    # Customer pays via the hosted link (not auto-charge), so it must be send_invoice.
    client = _FakeClient()
    await _provider(client).create_invoice(_request())
    inv = client.v1.invoices.create_calls[0]["params"]
    assert inv["collection_method"] == "send_invoice"


# --- webhook verification ---------------------------------------------------
def test_parse_webhook_requires_a_signing_secret():
    p = _provider(webhook_secret="")
    with pytest.raises(ValueError, match="STRIPE_WEBHOOK_SECRET"):
        p.parse_webhook_event(b"{}", signature="t=1,v1=abc")


def test_parse_webhook_bad_signature_raises_valueerror(monkeypatch):
    def _boom(payload, sig, secret):
        raise ValueError("bad sig")

    monkeypatch.setattr("stripe.Webhook.construct_event", _boom)
    with pytest.raises(ValueError):
        _provider().parse_webhook_event(b"{}", signature="t=1,v1=bad")


def test_parse_webhook_success_returns_event(monkeypatch):
    event = {
        "id": "evt_1",
        "type": "invoice.paid",
        "data": {"object": {"id": "in_test_1", "metadata": {"order_id": "LK-AE-2001"}}},
    }
    monkeypatch.setattr("stripe.Webhook.construct_event", lambda payload, sig, secret: event)
    result = _provider().parse_webhook_event(json.dumps(event).encode(), signature="t=1,v1=ok")
    assert result.type == "invoice.paid"
    assert result.data["metadata"]["order_id"] == "LK-AE-2001"
    assert result.is_mock is False
