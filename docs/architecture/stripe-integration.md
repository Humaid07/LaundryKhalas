# Architecture — Stripe Payments (Invoicing + Tax)

Status: **Phase A + B built (mock-first, test-mode capable).** Not wired to the
booking flow yet. Live mode requires founder sign-off. See the
[build report](../build-reports/2026-08-05-stripe-integration.md).

## Principle: one mock-first boundary (mirrors the LLM layer)
No code outside `services/payments/` imports the `stripe` SDK. Everything obtains a
gateway via `services.payments.get_gateway()`, which returns:

- `MockStripeGateway` — deterministic, no I/O, no key (**the default**, and what all
  tests use); or
- `StripeProvider` — real Stripe calls, selected **only** when `settings.stripe_live_ready`
  (i.e. `STRIPE_MODE` is `test`/`live` **and** a key is present).

```
booking / webhook code
        │  get_gateway()
        ▼
services/payments/gateway.py ──► MockStripeGateway   (STRIPE_MODE=mock, default)
                              └─► StripeProvider      (STRIPE_MODE=test|live + key)
                                     │ stripe-python v1 async
                                     ▼
                                  Stripe API
```

## Surface: Invoicing + Stripe Tax
Chosen for VAT-compliant records in UAE/GCC. Flow in `StripeProvider.create_invoice`:
1. `customers.create` — with address (country/city) for **Stripe Tax**.
2. `invoice_items.create` — one per line, amounts in **minor units** (fils/cents).
3. `invoices.create` — `collection_method="send_invoice"`, `metadata.order_id`,
   `automatic_tax` **only when requested**. **Never** `payment_method_types`.
4. `invoices.finalize_invoice` — yields `hosted_invoice_url` + PDF (the WhatsApp link).

Every create carries an **idempotency key** derived from the order id, so a retried
turn never double-creates. Checkout Sessions are deferred.

## Settlement webhook: `POST /webhooks/stripe`
Signature verified via the gateway (`STRIPE_WEBHOOK_SECRET`; the mock parses JSON
offline). Maps the invoice back to an order by `metadata.order_id`, else by the linked
`stripe_invoice_id`. `invoice.paid` → `payment_status=paid` (+ `paid_at`,
`amount_paid_minor`); `invoice.payment_failed` → `failed`. **Idempotent** (a repeated
paid event is a no-op) and always **acknowledges** unknown/ignored events with 200 so
Stripe stops retrying. Never auth-gated.

## Data model (migration 000041 + `models.py` Order)
`stripe_customer_id`, `stripe_invoice_id` (indexed), `stripe_hosted_invoice_url`,
`stripe_invoice_pdf_url`, `payment_status` (CHECK `unpaid|pending|paid|failed|refunded|
void`), `amount_paid_minor`, `payment_currency`, `paid_at`. Backend/webhook-authoritative
— the WhatsApp model never writes them. Layers on the Phase 2b payment-preference
columns (migration 000040).

## Config (`settings.py`, all `STRIPE_*`)
`stripe_mode` (mock|test|live) · `stripe_secret_key` · `stripe_webhook_secret` ·
`stripe_api_version` (pinned `2026-07-29.dahlia`) · `stripe_default_currency` (aed) ·
`stripe_automatic_tax_enabled` (**default off**). `validate_stripe_config()` fails fast
on test/live without a key or on a mode/key-prefix mismatch. `stripe_status` is a
secret-free snapshot for health endpoints.

## Security
Keys only in `.env`/vault, never code or chat; prefer restricted (`rk_`) keys, test
first. Webhook signature always verified. Only the fields present are sent to Stripe
(privacy firewall). Facility/driver outputs never include payment data.

## Stripe Tax — the one trap to remember
`automatic_tax` collects tax **only** where an **active registration** exists; enabling
it without one silently collects nothing. So tax stays **off** until registrations are
added (UAE/Qatar first) and the switch is deliberately turned on. Product tax codes must
come from Stripe's canonical list — never hardcoded. Registration obligations are a tax
advisor's call, not ours.

## Deferred
Booking-flow wiring (create + send link via the approval gate) · Tax registrations ·
Checkout/subscriptions/Connect · refunds API · admin payment UI · `stripe_events` dedupe
table · applying 000041 to Supabase.
