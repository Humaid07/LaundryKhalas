"""Manual verification — create a real TEST-MODE Stripe invoice via the gateway.

Safe by construction: it refuses to run unless STRIPE_MODE is 'test' (never live),
and it makes NO charge — it only creates + finalizes a hosted invoice and prints the
pay link. Use it to confirm the sandbox connection and Stripe Tax end to end.

Prerequisites (never commit real keys):
    STRIPE_MODE=test
    STRIPE_SECRET_KEY=rk_test_...        # from the sandbox (acct_1U0Hz7J3O1LiJS3C)
    STRIPE_WEBHOOK_SECRET=whsec_...       # optional here; needed for the webhook

Run:
    ./.venv/Scripts/python.exe scripts/verify_stripe_invoice.py
"""
from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path

# Make the app root importable when run as `python scripts/verify_stripe_invoice.py`
# (sys.path[0] would otherwise be scripts/, hiding settings.py / services/).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.payments import InvoiceLineItem, InvoiceRequest, PaymentCustomer, get_gateway  # noqa: E402
from settings import get_settings  # noqa: E402


async def main() -> int:
    settings = get_settings()
    if settings.stripe_mode_normalized != "test":
        print(
            f"Refusing to run: STRIPE_MODE={settings.stripe_mode_normalized!r} "
            "(this script only runs in test mode). Set STRIPE_MODE=test in .env."
        )
        return 2
    if not settings.stripe_live_ready:
        print("STRIPE_SECRET_KEY is not set — add the sandbox test key to .env.")
        return 2

    gateway = get_gateway()
    print(f"gateway = {gateway.name}  (automatic_tax={settings.stripe_automatic_tax_effective})")

    # Unique per run so repeated verifications don't collide on Stripe's
    # idempotency keys (a key can't be reused with different parameters).
    run_id = uuid.uuid4().hex[:8]

    request = InvoiceRequest(
        customer=PaymentCustomer(
            name="Test Customer",
            email="test.customer@example.com",
            country="AE",
            city="Dubai",
        ),
        line_items=[
            InvoiceLineItem(description="Wash & Fold 6kg", amount_minor=5400),
            InvoiceLineItem(description="Express surcharge", amount_minor=1500),
        ],
        currency=settings.stripe_default_currency,
        order_id=f"LK-AE-VERIFY-{run_id}",
        automatic_tax=settings.stripe_automatic_tax_effective,
        idempotency_key=f"LK-AE-VERIFY-{run_id}",
    )

    result = await gateway.create_invoice(request)
    print("\n--- invoice created ---")
    print("invoice_id :", result.invoice_id)
    print("customer   :", result.customer_id)
    print("status     :", result.status)
    print("amount_due :", result.amount_due_minor, result.currency)
    print("PAY LINK   :", result.hosted_invoice_url)
    print("PDF        :", result.invoice_pdf_url)
    print("\nOpen the PAY LINK in a browser and pay with test card 4242 4242 4242 4242.")
    print("Run `stripe listen --forward-to localhost:8100/webhooks/stripe` to settle the order.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
