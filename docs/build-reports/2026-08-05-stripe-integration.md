# Build Report — Stripe Integration (Payments · Invoicing · Tax), Phase A + B

**Date:** 2026-08-05
**Author:** Engineering (Claude, pair with founder)
**Related:** [[project_2026-08-05_phase2b-stripe-first-payment]] · spec §13 · [[stripe-integration]] (architecture)

---

## 1. Task objective
Stand up a real Stripe integration for the WhatsApp Operations Agent, moving the
existing **mock-only** payment-preference engine toward actual payment collection.
Founder-approved scope (overriding the standing mock-first rule for this module):

- **Payments + Invoicing + Tax**, surface = **Stripe Invoicing** (hosted VAT invoice
  + PDF whose pay link is sent over WhatsApp).
- **Phase A** — config + gateway + deterministic mock provider (no live calls).
- **Phase B** — real test-mode Invoicing calls, `/webhooks/stripe`, DB migration.
- Test credentials via the Stripe **sandbox** (`acct_1U0Hz7J3O1LiJS3C`, "LAUNDRYKHALAS sandbox").

Not in scope: Checkout Sessions, subscriptions, Connect/partner payouts, live-mode keys.

## 2. What was built
1. A **mock-first payments layer** (`services/payments/`) mirroring the LLM layer:
   one gateway boundary, a real provider selected ONLY when `STRIPE_MODE` is
   test/live with a key, else a deterministic offline mock.
2. `STRIPE_MODE` config + fail-fast validation (test/live require a mode-matching key).
3. The real **StripeProvider** (Invoicing + Stripe Tax) using the stripe-python v1
   async API, with idempotency keys and best-practice params.
4. A signature-verified, idempotent **`/webhooks/stripe`** settlement route.
5. **Migration 000041** + Order ORM columns for Stripe/settlement state.
6. **33 new tests**, all green offline.

## 3. Why
The payment-preference engine (`services/payment_preference.py`) already decides
*Stripe vs cash* and promises "we'll send the Stripe payment link once your order is
ready" — but no code created a link. This build supplies that link workflow behind a
safe, mock-first, config-gated boundary so nothing goes live by accident.

## 4. Files created
- `apps/whatsapp-agent/services/payments/__init__.py`
- `apps/whatsapp-agent/services/payments/base.py` — types + `StripeGateway` interface
- `apps/whatsapp-agent/services/payments/mock_provider.py` — `MockStripeGateway`
- `apps/whatsapp-agent/services/payments/gateway.py` — `get_gateway()` selector
- `apps/whatsapp-agent/services/payments/stripe_provider.py` — live `StripeProvider`
- `apps/whatsapp-agent/api/stripe_webhooks.py` — `POST /webhooks/stripe`
- `supabase/migrations/20260805_000041_orders_stripe_invoicing.sql`
- `apps/whatsapp-agent/tests/test_stripe_gateway.py` (16)
- `apps/whatsapp-agent/tests/test_stripe_provider.py` (10)
- `apps/whatsapp-agent/tests/test_stripe_webhooks.py` (7)

## 5. Files modified
- `apps/whatsapp-agent/settings.py` — `STRIPE_MODES`, 6 `stripe_*` fields, gating
  properties (`stripe_mode_normalized`, `stripe_live_ready`, `stripe_status`…),
  `validate_stripe_config()`.
- `apps/whatsapp-agent/main.py` — call `validate_stripe_config()` at startup;
  register `stripe_webhooks.router` (un-guarded).
- `apps/whatsapp-agent/models.py` — `Order` gains `stripe_customer_id`,
  `stripe_invoice_id`, `stripe_hosted_invoice_url`, `stripe_invoice_pdf_url`,
  `payment_status`, `amount_paid_minor`, `payment_currency`, `paid_at`.
- `apps/whatsapp-agent/pyproject.toml` — `stripe>=15.4.0`.

## 6. API endpoints added
- `POST /webhooks/stripe` — Invoicing settlement. Signature-verified, never
  auth-gated, idempotent. Handles `invoice.paid` / `invoice.payment_succeeded`
  (→ order `paid`) and `invoice.payment_failed` (→ `failed`); all other events are
  acknowledged (200) and ignored. Unmatched/unknown orders are acknowledged so
  Stripe stops retrying (never 500).

## 7. Database changes
- Migration **000041** adds to `orders`: `stripe_customer_id`, `stripe_invoice_id`
  (indexed), `stripe_hosted_invoice_url`, `stripe_invoice_pdf_url`, `payment_status`
  (default `unpaid`, CHECK `unpaid|pending|paid|failed|refunded|void`),
  `amount_paid_minor`, `payment_currency`, `paid_at`. Idempotent (`add column if not
  exists`). Mirrored in the SQLite ORM (`models.py`). **Not yet applied to Supabase**
  (see §15).

## 8. Agent behavior
No customer-facing behavior change yet. The gateway is built and tested but **not
wired into the booking flow** (deferred — see §15). The payment-preference engine is
unchanged.

## 9. What is mock-only
- Default `STRIPE_MODE=mock` → `MockStripeGateway`: deterministic invoice ids/URLs,
  no network, no key. This is what the entire test suite and local dev use.

## 10. What is live-capable (but off by default)
- `StripeProvider` performs real Stripe API calls **only** when `STRIPE_MODE=test|live`
  AND `STRIPE_SECRET_KEY` is set. `live` mode additionally needs a `_live_` key and is
  intended only after founder sign-off + the Stripe go-live checklist.

## 11. What is intentionally deferred
- Wiring the gateway into the booking/confirmation flow (create invoice when
  preference locks `STRIPE` and the order is ready; send link via the approval gate).
- Stripe **Tax registrations** (UAE/Qatar) — `automatic_tax` stays **off** until a
  registration exists (enabling it without one silently collects nothing).
- Checkout Sessions, subscriptions, Connect payouts, refunds via API.
- Admin dashboard payment visibility / "Live Stripe: On/Off" badge.
- A dedicated `stripe_events` dedupe table (current idempotency is via order state).
- Applying migration 000041 to Supabase.

## 12–13. Tests run / results
- `tests/test_stripe_gateway.py` — **16 passed** (config gating + mock gateway).
- `tests/test_stripe_provider.py` — **10 passed** (live flow vs injected fake client:
  invoicing sequence, automatic_tax on/off, **never** `payment_method_types`,
  idempotency keys, metadata, webhook verify).
- `tests/test_stripe_webhooks.py` — **7 passed** (paid/failed settlement, idempotency,
  unmatched-order ack, 400 on bad payload, match by invoice id).
- **Live sandbox verification (real test-mode call, `acct_1U0Hz7J3O1LiJS3C`):**
  `scripts/verify_stripe_invoice.py` created a real invoice — `status=open`,
  `amount_due=6900 aed` (AED 69.00), real `invoice.stripe.com` hosted pay link.
- Full suite: not run to completion locally (a concurrent Claude session was running
  it in the same repo, sharing the SQLite test DB → lock contention). Targeted stripe
  + payment-preference slices are green.

## 14. Bugs/issues found
- **Empty-invoice bug (found by the live sandbox check, not unit tests):** invoice
  items created as "pending" (customer-only) were NOT pulled into the invoice, so
  Stripe finalized a $0 invoice and auto-marked it `paid`. **Fixed** — create the
  draft invoice first, then attach each item with `invoice=<id>`, then finalize.
  Re-verified live (`amount_due=6900`). The unit test now asserts items carry the
  invoice id.
- **Suite hermeticity:** once `.env` had `STRIPE_MODE=test` + a key (for live work),
  the test suite picked it up and the webhook route selected the real provider →
  400s. **Fixed** by pinning `STRIPE_MODE=mock` in `tests/conftest.py` (same pattern
  as the existing `DATABASE_MODE`/`WHATSAPP_MODE` pins).
- **`.env` paste corruption:** the pasted secret key had stray spaces (a leading
  space and `_`→space); normalized by stripping whitespace on that line. Key values
  must contain no whitespace.
- Initial `stripe` install went to the **system** Python, not the project `.venv`;
  reinstalled into `.venv`. Recorded `stripe>=15.4.0` in `pyproject.toml`.
- Concurrent pytest runs share one SQLite test DB → file-lock timeouts. Not a code
  bug; avoid running two suites at once.

## 15. Known limitations
- Settlement writes go through the ORM session (`get_db`), which works for SQLite and
  for Supabase when `DATABASE_URL` points at Postgres. A native asyncpg-repo path was
  not added.
- Migration 000041 must be applied to Supabase before test/live use there.
- End-to-end against the real sandbox needs an interactive CLI login (or a test key in
  `.env`) — see §23.

## 16. Security / privacy notes
- **No key in code or chat.** `STRIPE_SECRET_KEY`/`STRIPE_WEBHOOK_SECRET` live only in
  `.env` (gitignored) or a secrets vault. `stripe_status` never echoes the key.
  Recommended: a **restricted** key (`rk_`), test mode first.
- Mode/key mismatch (a `_live_` key in test mode, or vice versa) fails fast at startup.
- Webhook signature is always verified (`stripe.Webhook.construct_event`); a missing
  secret or bad signature is rejected (400), never processed.
- Privacy firewall: the provider sends Stripe only the fields present (name/email/phone
  + country/city for Tax). Facility/driver views never receive payment data.
- `payment_method_types` is never sent → dynamic payment methods (Dashboard-managed).

## 17. Cost / LLM usage notes
- No LLM usage in this build. No live Stripe charges (mock default; test mode uses
  test data only). Stripe test-mode API calls are free.

## 18. Screens/pages to demo
- None yet (no UI in this build). Demo is code + tests + (optionally) a hosted test
  invoice URL once the sandbox is connected.

## 19. Commands to run
```bash
cd apps/whatsapp-agent
./.venv/Scripts/python.exe -m pytest tests/test_stripe_gateway.py \
    tests/test_stripe_provider.py tests/test_stripe_webhooks.py -q
```

## 20. How to verify manually (real test-mode, sandbox acct_1U0Hz7J3O1LiJS3C)
1. Install + authenticate the Stripe CLI to the sandbox: `stripe login` (interactive),
   or `stripe sandbox claim`.
2. Put the sandbox **test** key + webhook secret into `.env` (never commit):
   `STRIPE_MODE=test`, `STRIPE_SECRET_KEY=rk_test_…`, `STRIPE_WEBHOOK_SECRET=whsec_…`.
3. Create a test invoice via the gateway and open its `hosted_invoice_url`.
4. `stripe listen --forward-to localhost:8100/webhooks/stripe`, pay with test card
   `4242 4242 4242 4242` (or `stripe trigger invoice.paid`), confirm the order flips
   to `paid`.

## 21. Next recommended step
Wire the gateway into the booking flow behind the existing admin-approval gate (create
the invoice when preference = `STRIPE` and the order is ready), then add Stripe Tax
registrations for the live markets.
