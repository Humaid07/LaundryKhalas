"""The live Stripe gateway — Invoicing + Stripe Tax.

Reached ONLY through ``services.payments.get_gateway()`` when STRIPE_MODE is
test/live with a key. Uses the stripe-python v1 service namespace + its native
async methods (no threadpool). Every create carries an idempotency key so a
retried WhatsApp turn never double-creates.

Best-practices enforced here (from Stripe's own guidance):
  * The customer pays via the hosted invoice link → collection_method="send_invoice".
  * automatic_tax is set ONLY when the caller asks (config-gated), never guessed —
    enabling it without a tax registration silently collects nothing.
  * `payment_method_types` is NEVER sent → dynamic payment methods (managed in the
    Dashboard) pick the best methods per customer.
  * The webhook signature is always verified against STRIPE_WEBHOOK_SECRET.
"""
from __future__ import annotations

import stripe

from services.payments.base import (
    InvoiceRequest,
    InvoiceResult,
    StripeGateway,
    WebhookEvent,
)

# Customer pays the hosted invoice by link; give a due window rather than an
# immediate auto-charge (we hold no saved card).
_DAYS_UNTIL_DUE = 7


class StripeProvider(StripeGateway):
    name = "stripe"

    def __init__(
        self,
        *,
        api_key: str,
        api_version: str,
        default_currency: str = "aed",
        webhook_secret: str = "",
        client=None,
    ):
        self._default_currency = (default_currency or "aed").lower()
        self._webhook_secret = webhook_secret
        # `client` is injectable so tests exercise the flow with no network. In
        # production we build a StripeClient pinned to the configured API version
        # so the payload shape can't drift under us.
        self._client = client or stripe.StripeClient(api_key, stripe_version=api_version)

    def _opts(self, request: InvoiceRequest, suffix: str) -> dict | None:
        base_key = request.idempotency_key or request.order_id
        if not base_key:
            return None
        return {"idempotency_key": f"{base_key}:{suffix}"}

    async def create_invoice(self, request: InvoiceRequest) -> InvoiceResult:
        v1 = self._client.v1
        currency = (request.currency or self._default_currency).lower()

        # 1. Customer — carry the tax-relevant address (Stripe Tax resolves the
        #    rate from it). Only send fields we actually have (privacy firewall).
        cust_params: dict = {"name": request.customer.name}
        if request.customer.email:
            cust_params["email"] = request.customer.email
        if request.customer.phone:
            cust_params["phone"] = request.customer.phone
        address = {}
        if request.customer.country:
            address["country"] = request.customer.country
        if request.customer.city:
            address["city"] = request.customer.city
        if request.customer.address_line1:
            address["line1"] = request.customer.address_line1
        if request.customer.postal_code:
            address["postal_code"] = request.customer.postal_code
        if address:
            cust_params["address"] = address
        customer = await v1.customers.create_async(
            cust_params, options=self._opts(request, "cust")
        )

        # 2. Invoice (draft) FIRST — so items can be attached to it explicitly.
        #    Relying on "pending" items (customer-only) to be auto-pulled is
        #    unreliable and finalizes an empty $0 invoice. NO payment_method_types.
        inv_params: dict = {
            "customer": customer.id,
            "collection_method": "send_invoice",
            "days_until_due": _DAYS_UNTIL_DUE,
            "auto_advance": False,
            "metadata": {"order_id": request.order_id or ""},
        }
        if request.automatic_tax:
            inv_params["automatic_tax"] = {"enabled": True}
        invoice = await v1.invoices.create_async(
            inv_params, options=self._opts(request, "inv")
        )

        # 3. Invoice items — one per line, amounts in minor units, each attached
        #    to THIS draft invoice via invoice=<id>.
        for idx, line in enumerate(request.line_items):
            await v1.invoice_items.create_async(
                {
                    "customer": customer.id,
                    "invoice": invoice.id,
                    "amount": line.total_minor,
                    "currency": currency,
                    "description": line.description,
                },
                options=self._opts(request, f"li:{idx}"),
            )

        # 4. Finalize → produces the hosted_invoice_url + PDF sent to the customer.
        finalized = await v1.invoices.finalize_invoice_async(invoice.id)

        return InvoiceResult(
            provider=self.name,
            invoice_id=finalized.id,
            hosted_invoice_url=getattr(finalized, "hosted_invoice_url", None),
            invoice_pdf_url=getattr(finalized, "invoice_pdf", None),
            status=getattr(finalized, "status", "open"),
            amount_due_minor=int(getattr(finalized, "amount_due", request.total_minor) or 0),
            currency=getattr(finalized, "currency", currency),
            customer_id=customer.id,
            is_mock=False,
        )

    def parse_webhook_event(self, payload: bytes, signature: str | None) -> WebhookEvent:
        if not (self._webhook_secret or "").strip():
            raise ValueError(
                "STRIPE_WEBHOOK_SECRET not configured; cannot verify webhook signature."
            )
        try:
            event = stripe.Webhook.construct_event(payload, signature, self._webhook_secret)
        except Exception as exc:  # noqa: BLE001 - any verify failure → 400 at the route
            raise ValueError(f"invalid Stripe webhook signature: {exc}") from exc
        obj = (event.get("data") or {}).get("object") or {}
        return WebhookEvent(
            id=str(event.get("id", "")),
            type=str(event.get("type", "")),
            data=dict(obj) if hasattr(obj, "keys") else {},
            is_mock=False,
        )
