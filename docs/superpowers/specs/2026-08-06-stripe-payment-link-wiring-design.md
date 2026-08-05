# Design — Admin-triggered Stripe payment link (booking-flow wiring)

**Date:** 2026-08-06
**Depends on:** the committed Stripe layer (`services/payments/`, `POST /webhooks/stripe`,
migration 000041) — see `docs/architecture/stripe-integration.md`.

## Goal
Let ops create + send a Stripe pay-link for a confirmed `STRIPE`-preference order from
the admin order detail (`PaymentSnapshotCard`). Chosen behaviour (owner, 2026-08-06):
**admin-triggered**, **one-click create + queue for approval** (draft a pending message,
approve to send). No auto-creation at confirmation/ready.

## Components

### 1. `services/payments/invoicing.py`
- `build_invoice_request(order_row) -> (InvoiceRequest | None, reason: str | None)` —
  **pure, no I/O** (fully unit-testable). Returns `(None, reason)` when ineligible.
  Eligibility: order is confirmed (`status` not in draft/cancelled/abandoned),
  `payment_preference == "STRIPE"`, a positive `amount`, and no existing
  `stripe_invoice_id` (already-invoiced → skip). Builds:
  - amount → **minor units** (`round(amount * 100)`), a single summary line item
    `"Order {order_id} — {service_type}"`.
  - customer name/phone from the order.
  - **country from the order-id market prefix** (`LK-AE-…` → `AE`, `LK-QA-…` → `QA`)
    for Stripe Tax; city from `city`/`pickup_area`.
  - `automatic_tax = settings.stripe_automatic_tax_effective` (off by default).
  - `idempotency_key = order_id`.
- `ensure_invoice_for_order(order_row) -> InvoiceResult | None` — thin orchestration:
  pure builder → `get_gateway().create_invoice()` → persist
  `stripe_customer_id / stripe_invoice_id / stripe_hosted_invoice_url /
  stripe_invoice_pdf_url / payment_status='pending' / payment_currency` + an
  `order_events` row (`payment_link_created`). **Idempotent** (existing invoice → return
  it, no second Stripe call). Never raises into the caller; returns None on guard-fail.

### 2. Endpoints (ops-guarded, Supabase-mode) — in `api/orders.py`
- `POST /api/orders/{order_id}/payment-link` → `ensure_invoice_for_order` + draft the
  payment message as a **pending** outbound (stored, not sent). Returns
  `{invoice_id, hosted_url, pdf_url, draft_message}`. 409 with reason when ineligible;
  502 on gateway failure (nothing persisted).
- `POST /api/orders/{order_id}/payment-link/approve` → send the pending message via
  `EvolutionWhatsAppChannel` (reusing `human-message` send + takeover), mark `sent`.
  Mock/non-live → stored (`send_status: stored`).

Message text (reply-style compliant: no dash/emoji/exclamation), e.g.:
`"Hi {name}, your order {order_id} is ready for payment. You can pay {amount} {CUR}
securely by card here: {url}. No account is needed."`

### 3. Admin UI — `PaymentSnapshotCard`
"Create payment link" (confirmed STRIPE + no link) → shows link + "Approve & send".
Typed against the order DTO; reuses the existing card.

## Data flow
`confirm_order` (sets `payment_preference=STRIPE`) → ops **Create payment link** →
invoice + pending draft → ops **Approve & send** → customer gets `invoice.stripe.com`
link → pays → `/webhooks/stripe` flips order to `paid`.

## Error handling
Gateway failure → 502, order untouched. Not-confirmed/not-STRIPE/no-amount → 409 + reason.
Re-click after a link exists → returns existing link (idempotent). Evolution not live →
stores, doesn't send.

## Testing
- **Pure `build_invoice_request`:** full TDD in the hermetic sqlite suite — eligibility
  guards, minor-units conversion, tax-country from prefix, single line item,
  already-invoiced skip.
- **Gateway interaction:** via the mock gateway.
- Endpoint/persistence is Supabase-only (like §29 order-detail); kept thin and verified
  against the mock gateway; guard paths asserted.

## Scope-out (YAGNI)
No general approval queue (narrow payment-message flow only). No auto-trigger. No
itemized invoice lines (single summary line). No Tax registrations (separate task).
