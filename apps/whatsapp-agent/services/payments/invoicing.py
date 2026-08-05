"""Order -> Stripe invoice orchestration (admin-triggered payment link).

Two layers, split for testability:
  * ``build_invoice_request`` — PURE. Eligibility guards + the order-row -> InvoiceRequest
    mapping. No I/O; fully unit-tested offline.
  * ``ensure_invoice_for_order`` — thin orchestration: pure builder -> gateway ->
    persist the invoice linkage on the order. Idempotent (an order that already has a
    ``stripe_invoice_id`` is returned as-is, no second Stripe call). Supabase-mode.

The gateway is mock-first (services.payments.get_gateway), so in mock mode this creates
a deterministic fake invoice with no network. Never invents payment data — the amount
comes from the order, and the settlement truth still arrives only via /webhooks/stripe.
"""
from __future__ import annotations

import re

import structlog

from services.payments.base import (
    InvoiceLineItem,
    InvoiceRequest,
    InvoiceResult,
    PaymentCustomer,
)
from services.payments.gateway import get_gateway

logger = structlog.get_logger()

# A payment link only makes sense for an in-flight, confirmed order — never a bare
# draft, and never a terminal (cancelled/abandoned/completed) one.
_INELIGIBLE_STATUSES = {"draft", "cancelled", "abandoned", "completed"}
# Business order ids embed the market: LK-AE-1024 / LK-QA-2001. The 2-letter code is
# the ISO country Stripe Tax resolves the rate from.
_ORDER_ID_MARKET = re.compile(r"^LK-([A-Za-z]{2})-")


def _country_from_order_id(order_id: str | None) -> str | None:
    match = _ORDER_ID_MARKET.match(order_id or "")
    return match.group(1).upper() if match else None


def build_invoice_request(
    order_row: dict, *, automatic_tax: bool = False
) -> tuple[InvoiceRequest | None, str | None]:
    """Build the InvoiceRequest for an order, or return (None, human reason) when the
    order is not eligible for a payment link. Pure: no I/O, no settings access."""
    status = str(order_row.get("status") or "").strip().lower()
    if not status or status in _INELIGIBLE_STATUSES:
        return None, f"order is not confirmed / eligible (status={status or 'unknown'!r})"

    if str(order_row.get("payment_preference") or "").strip().upper() != "STRIPE":
        return None, "payment preference is not STRIPE (no card link to create)"

    if order_row.get("stripe_invoice_id"):
        return None, "an invoice already exists for this order"

    amount = order_row.get("amount")
    try:
        amount_val = float(amount) if amount is not None else 0.0
    except (TypeError, ValueError):
        amount_val = 0.0
    if amount_val <= 0:
        return None, "order has no amount to invoice yet"

    order_id = str(order_row.get("order_id") or "")
    service = (str(order_row.get("service_type") or "").strip() or "Laundry")
    currency = str(order_row.get("currency") or "aed").strip().lower()

    customer = PaymentCustomer(
        name=str(order_row.get("customer_name") or "Customer"),
        phone=(order_row.get("customer_phone") or None),
        country=_country_from_order_id(order_id),
        city=(order_row.get("city") or order_row.get("pickup_area") or None),
    )
    line = InvoiceLineItem(
        description=f"{service} for order {order_id}",
        amount_minor=round(amount_val * 100),
    )
    request = InvoiceRequest(
        customer=customer,
        line_items=[line],
        currency=currency,
        order_id=order_id,
        automatic_tax=automatic_tax,
        idempotency_key=(order_id or None),
    )
    return request, None


async def ensure_invoice_for_order(order_row: dict) -> InvoiceResult | None:
    """Create (once) a Stripe invoice for a confirmed STRIPE order and persist its
    linkage. Returns the InvoiceResult, or None when the order is ineligible (the
    reason is logged). Never raises into the caller.

    Idempotent: an order that already carries a ``stripe_invoice_id`` short-circuits in
    the pure builder, so this is safe to call more than once."""
    from settings import get_settings

    settings = get_settings()
    request, reason = build_invoice_request(
        order_row, automatic_tax=settings.stripe_automatic_tax_effective
    )
    if request is None:
        logger.info("payment_link_skipped", order=order_row.get("order_id"), reason=reason)
        return None

    result = await get_gateway().create_invoice(request)

    # Persist the invoice linkage on the order (Supabase). Best-effort: a persistence
    # failure must not lose the created invoice — it's logged and the result returned.
    from db import database

    order_uuid = str(order_row.get("id"))
    try:
        await database.execute(
            "update orders set stripe_customer_id = $1, stripe_invoice_id = $2, "
            "stripe_hosted_invoice_url = $3, stripe_invoice_pdf_url = $4, "
            "payment_status = 'pending', payment_currency = $5, updated_at = now() "
            "where id = $6",
            result.customer_id, result.invoice_id, result.hosted_invoice_url,
            result.invoice_pdf_url, result.currency, order_uuid,
        )
        await database.execute(
            "insert into order_events (order_id, event_type, actor_type, metadata) "
            "values ($1, 'payment_link_created', 'operator', $2::jsonb)",
            order_uuid,
            _event_metadata(result),
        )
    except Exception as exc:  # noqa: BLE001 - never lose the created invoice
        logger.warning(
            "payment_link_persist_failed", order=order_row.get("order_id"),
            invoice=result.invoice_id, error=str(exc),
        )
    return result


def render_payment_message(
    *, name: str, order_id: str, amount_major: float, currency: str, hosted_url: str
) -> str:
    """The customer-facing payment-link message drafted for operator approval.
    Reply-style compliant (no emoji / exclamation): a plain, clear card-payment
    prompt. Operator-reviewed before sending, so it never auto-sends."""
    greet = (name or "").strip() or "there"
    amount = f"{float(amount_major):.2f} {currency.upper()}"
    return (
        f"Hi {greet}, your order {order_id} is ready for payment. "
        f"You can pay {amount} securely by card here: {hosted_url}. "
        f"No account is needed."
    )


def _event_metadata(result: InvoiceResult) -> str:
    import json

    return json.dumps({
        "invoice_id": result.invoice_id,
        "provider": result.provider,
        "amount_due_minor": result.amount_due_minor,
        "currency": result.currency,
        "is_mock": result.is_mock,
    })
