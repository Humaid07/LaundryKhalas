"""Deterministic, offline Stripe gateway — the mock-first default.

Creates no network traffic and needs no key. Ids/URLs are derived from the
request so the same order yields the same invoice id (idempotent-looking), which
keeps tests and local demos stable. This is what runs everywhere unless
STRIPE_MODE is test/live with a key present.
"""
from __future__ import annotations

import hashlib
import json

from services.payments.base import (
    InvoiceRequest,
    InvoiceResult,
    StripeGateway,
    WebhookEvent,
)

_MOCK_INVOICE_HOST = "https://invoice.mock.laundrykhalas.local"


def _digest(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:16]


class MockStripeGateway(StripeGateway):
    name = "mock"

    async def create_invoice(self, request: InvoiceRequest) -> InvoiceResult:
        seed = request.idempotency_key or request.order_id or _digest(
            request.customer.name, str(request.total_minor)
        )
        invoice_id = f"in_mock_{_digest(seed)}"
        customer_id = f"cus_mock_{_digest(request.customer.email or request.customer.name)}"
        hosted = f"{_MOCK_INVOICE_HOST}/{invoice_id}"
        return InvoiceResult(
            provider=self.name,
            invoice_id=invoice_id,
            hosted_invoice_url=hosted,
            invoice_pdf_url=f"{hosted}/pdf",
            status="open",
            amount_due_minor=request.total_minor,
            currency=request.currency.lower(),
            customer_id=customer_id,
            is_mock=True,
        )

    def parse_webhook_event(self, payload: bytes, signature: str | None) -> WebhookEvent:
        """Mock verification: no signing secret, just parse the JSON envelope.
        Shapes match Stripe's ``{id, type, data: {object: {...}}}`` so the route
        handler is identical in mock and live."""
        try:
            body = json.loads(payload.decode("utf-8") if isinstance(payload, bytes) else payload)
        except (json.JSONDecodeError, UnicodeDecodeError, AttributeError) as exc:
            raise ValueError(f"unparseable mock webhook payload: {exc}") from exc
        if not isinstance(body, dict) or "type" not in body:
            raise ValueError("mock webhook payload missing 'type'")
        obj = ((body.get("data") or {}).get("object")) or {}
        return WebhookEvent(
            id=str(body.get("id", "evt_mock")),
            type=str(body["type"]),
            data=obj if isinstance(obj, dict) else {},
            is_mock=True,
        )
