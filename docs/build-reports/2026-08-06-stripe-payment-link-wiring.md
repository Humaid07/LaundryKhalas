# Build Report — Stripe payment link wired into the booking flow

**Date:** 2026-08-06
**Design:** `docs/superpowers/specs/2026-08-06-stripe-payment-link-wiring-design.md`
**Builds on:** the committed Stripe layer (`1973ccb` + wiring in `2e247ca`) — see
`docs/architecture/stripe-integration.md`.

## 1. Objective
Connect the (already-built, live-verified) Stripe gateway to the operations flow so
ops can create + send a card payment link for a confirmed `STRIPE`-preference order.
Owner decisions (2026-08-06): **admin-triggered**, **one-click create + queue for
approval** (draft a pending message; approve to send).

## 2. What was built
- **`services/payments/invoicing.py`**
  - `build_invoice_request(order_row, *, automatic_tax)` — **pure**: eligibility guards
    (confirmed status, `payment_preference==STRIPE`, positive amount, not already
    invoiced) + order→InvoiceRequest mapping (amount→minor units, single summary line
    item, tax **country from the `LK-AE`/`LK-QA` order-id prefix**).
  - `ensure_invoice_for_order(order_row)` — thin orchestration: pure builder →
    `get_gateway().create_invoice()` → persist invoice linkage + `order_events` row.
    **Idempotent** (existing `stripe_invoice_id` → skip, no second Stripe call).
  - `render_payment_message(...)` — pure, reply-style-compliant customer message.
- **Endpoints (`api/orders.py`, ops-guarded, Supabase-mode):**
  - `POST /api/orders/{order_id}/payment-link` — create invoice + draft a pending
    (`pending_approval`) pay-link message. Accepts business id **or** uuid. 409 with a
    reason when ineligible; 502 on gateway failure; idempotent when a link exists.
  - `POST /api/orders/{order_id}/payment-link/approve` — send the drafted message via
    the sanctioned human-send path (`EvolutionWhatsAppChannel` + takeover), mark `sent`.
- **Admin UI (`order-detail/cards.tsx` `PaymentSnapshotCard`):** a `PaymentLinkActions`
  block (shown for STRIPE orders) — **Create payment link** → shows the hosted link →
  **Approve & send**. New typed client methods + DTOs in `whatsapp-agent-api.ts`.

## 3. Files
Created: `services/payments/invoicing.py`, `tests/test_stripe_invoicing.py`,
`docs/superpowers/specs/2026-08-06-stripe-payment-link-wiring-design.md`, this report.
Modified: `api/orders.py` (endpoints + imports), `apps/admin/.../order-detail/cards.tsx`
(action component), `apps/admin/lib/dashboard/whatsapp-agent-api.ts` (methods + DTOs).

## 4. Data flow
`confirm_order` (sets `payment_preference=STRIPE`) → ops **Create payment link** →
invoice + pending draft → ops **Approve & send** → customer gets the `invoice.stripe.com`
link → pays → `/webhooks/stripe` flips the order to `paid`.

## 5. Mock vs live
Invoice creation is mock-first (`get_gateway()`): the deterministic mock in
`STRIPE_MODE=mock` (default + the whole test suite), the real provider only in
`test`/`live` with a key. Sending uses Evolution only when `evolution_live_ready`,
else stored (`send_status: stored`).

## 6. Tests
- `tests/test_stripe_invoicing.py` — **17 passed**: pure builder (guards, minor-units,
  tax-country, already-invoiced skip), `ensure_invoice_for_order` (mock gateway + a
  recorded `database.execute`), the pure message renderer, and the endpoint Supabase
  guard (registered + 400 in sqlite).
- Full Stripe backend set (gateway/provider/webhooks/invoicing): **50 passed**.
- Admin app: `tsc --noEmit` clean, `next lint` clean.

## 7. Deliberately scoped out (YAGNI)
No general approval queue (a narrow payment-message flow only). No auto-trigger at
confirmation/ready. Single summary invoice line (not itemized). Stripe Tax registrations
(separate task; `automatic_tax` stays off by default).

## 8. Known limitations
- Endpoints/persistence are **Supabase-only** (like the §29 order-detail surface); the
  pure builder + renderer carry the unit-tested logic. Full click-through needs the live
  stack (Supabase + backend + admin + Evolution).
- Re-creating a link for an order that already has one returns the existing link but does
  not mint a fresh approval draft in the same click.

## 9. Next recommended step
Manual end-to-end on the live stack (create → approve → pay a test invoice → webhook
settles), then Stripe Tax registrations (UAE/Qatar) before enabling `automatic_tax`.
