"""Provider-agnostic payment types + the gateway interface.

All amounts are in **minor units** (fils / cents) — the integer Stripe itself
uses — so there is never a float rounding ambiguity crossing the boundary. The
caller (booking/fulfilment) converts from services/money.Decimal totals once,
here, and nowhere downstream re-derives money.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

# --- payment_status vocabulary (mirrors the orders.payment_status CHECK) -----
UNPAID = "unpaid"
PENDING = "pending"
PAID = "paid"
FAILED = "failed"
REFUNDED = "refunded"
VOID = "void"

PAYMENT_STATUSES = (UNPAID, PENDING, PAID, FAILED, REFUNDED, VOID)


@dataclass(frozen=True)
class PaymentCustomer:
    """The minimal customer identity Stripe needs for an invoice + Stripe Tax.

    Privacy firewall: pass only what's required. ``country`` (ISO-3166 alpha-2)
    is what Stripe Tax resolves the rate from; finer address fields are optional
    and only sent when available (UAE VAT is a flat 5% domestic, so country is
    usually sufficient)."""
    name: str
    email: str | None = None
    phone: str | None = None
    country: str | None = None       # ISO-2, e.g. "AE" / "QA" — needed for Stripe Tax
    city: str | None = None
    address_line1: str | None = None
    postal_code: str | None = None


@dataclass(frozen=True)
class InvoiceLineItem:
    description: str
    amount_minor: int                # unit price in minor units (fils/cents)
    quantity: int = 1

    @property
    def total_minor(self) -> int:
        return int(self.amount_minor) * int(self.quantity)


@dataclass(frozen=True)
class InvoiceRequest:
    customer: PaymentCustomer
    line_items: list[InvoiceLineItem]
    currency: str = "aed"
    order_id: str | None = None      # our order id → stored as invoice metadata
    # When True the invoice enables Stripe Tax (automatic_tax). The gateway does
    # NOT decide whether a registration exists — the caller/config gates that, so
    # we never silently enable tax that collects nothing (the #1 Stripe Tax trap).
    automatic_tax: bool = False
    # Stable key so a retried create never double-charges/double-creates.
    idempotency_key: str | None = None

    @property
    def total_minor(self) -> int:
        return sum(li.total_minor for li in self.line_items)


@dataclass(frozen=True)
class InvoiceResult:
    provider: str                    # "mock" | "stripe"
    invoice_id: str
    hosted_invoice_url: str | None   # the link sent to the customer over WhatsApp
    invoice_pdf_url: str | None
    status: str                      # stripe invoice status: draft|open|paid|void|...
    amount_due_minor: int
    currency: str
    customer_id: str | None = None
    is_mock: bool = False


@dataclass(frozen=True)
class WebhookEvent:
    """A verified inbound Stripe event, reduced to what the handler needs.

    ``data`` is the event's ``data.object`` (e.g. the Invoice / Checkout Session)
    as a plain dict."""
    id: str
    type: str
    data: dict = field(default_factory=dict)
    is_mock: bool = False


class StripeGateway(ABC):
    """The single boundary every payment call crosses. Implemented by the
    deterministic ``MockStripeGateway`` and the live ``StripeProvider``; callers
    always obtain one via ``services.payments.get_gateway()`` and never import a
    concrete provider (mirrors llm/service.py)."""

    name: str

    @abstractmethod
    async def create_invoice(self, request: InvoiceRequest) -> InvoiceResult:
        """Create + finalize a hosted invoice and return its pay link. Real
        providers perform network I/O off the event loop; the mock is pure."""

    @abstractmethod
    def parse_webhook_event(self, payload: bytes, signature: str | None) -> WebhookEvent:
        """Verify the signature and return the event. Raises ValueError on an
        invalid signature or unparseable payload (the route maps that to 400)."""
