"""Payments layer — Stripe integration behind a single mock-first gateway.

Mirrors the LLM layer's discipline (llm/service.py): NO code outside this
package imports the ``stripe`` SDK directly, and a real Stripe provider is
selected ONLY when STRIPE_MODE is test/live AND a key is present. In mock mode
(the default) every call is served by the deterministic ``MockStripeGateway``
which performs no network I/O, so the whole test suite stays offline.

Surface (founder decision 2026-08-05): **Invoicing + Stripe Tax** — a hosted,
VAT-compliant invoice (hosted_invoice_url + PDF) whose link is sent to the
customer over WhatsApp. Checkout Sessions are intentionally deferred.
"""
from services.payments.base import (
    InvoiceLineItem,
    InvoiceRequest,
    InvoiceResult,
    PaymentCustomer,
    StripeGateway,
    WebhookEvent,
)
from services.payments.gateway import get_gateway

__all__ = [
    "InvoiceLineItem",
    "InvoiceRequest",
    "InvoiceResult",
    "PaymentCustomer",
    "StripeGateway",
    "WebhookEvent",
    "get_gateway",
]
