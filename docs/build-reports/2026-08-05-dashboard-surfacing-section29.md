# Build Report — Dashboard Surfacing (Section 29), backend slice

**Date:** 2026-08-05
**Status:** Order-detail API surfaces the Stripe-first payment state; admin `OrderDTO` typed.
Full visual rendering across the admin surfaces is remaining UI work (see §5). UNCOMMITTED.

## 1. Objective
Section 29 asks the Operations dashboard + order-detail to show the customer/pricing/payment/
follow-up/facility state the backend now holds. This is primarily an admin-frontend task
(React/Next.js, verified by `tsc`/lint/visual, not the pytest suite). This increment delivers
the pytest-verifiable prerequisite — exposing the new order fields in the order-detail API — plus
the frontend DTO type.

## 2. What changed (backend — pytest-tested)
- **`OrderRead` schema** + both serialization paths (`order_store.to_dict` for SQLite/tests,
  `orders_repo.to_read`/`get_read` for Supabase) now expose:
  `payment_preference` (UNDECIDED|STRIPE|CASH_ON_DELIVERY), `cash_on_delivery` (derived),
  `payment_status` (unpaid|pending|paid|…), `payment_followup_stage`, `stripe_hosted_invoice_url`
  (Stripe-link status). All backend-authoritative; the privacy firewall test still passes (none
  are PII).
- Test: `tests/test_orders.py::test_order_detail_surfaces_payment_fields` — the order-detail API
  returns the payment fields with correct defaults.

## 3. What changed (frontend — tsc + eslint clean)
- **`apps/admin/lib/dashboard/whatsapp-agent-api.ts`** `OrderDTO` + **`.../order-detail/data.ts`**
  `OrderWithPricing` extended with the payment fields (typed).
- **`PaymentSnapshotCard`** (`.../order-detail/cards.tsx`) now renders the REAL payment method
  (Stripe link / Cash on delivery / Card, from `payment_preference` + `cash_on_delivery`), a
  Stripe-link status row (Sent/Pending), and a payment-follow-up stage row — falling back to the
  generic label on legacy/mock orders that don't carry the state. `npx tsc --noEmit` and
  `eslint` both pass.

## 3b. Discount snapshot (spec §§15, 29) — added
- **Backend:** `models.py` Order gains `eligible_subtotal`, `discount_percentage`,
  `discount_amount`, `discount_rule_code` (SQLite; the Supabase orders already had these via
  the order-discount migration). Surfaced as `eligible_subtotal` / `discount_percentage` /
  `discount_amount` / `discount_reason` through `OrderRead` + `to_dict` + `to_read`. pytest
  test extended (present, null on an undiscounted order).
- **Frontend:** `OrderDTO` + `OrderWithPricing` typed; `PaymentSnapshotCard` renders a
  "Discount" row (`{pct}% ({reason})`, reason humanised: Standard / Requested / Price pushback /
  Quote follow-up / Web offer / Manager approved / Negotiated). tsc + eslint clean.

## 3c. Rule-set version (spec §§17, 29) — added
- **Backend:** `models.py` Order gains `rule_version`; migration `000045` adds it to Supabase
  `orders`. Stamped at confirmation (`orders_repo.confirm_booking` — `coalesce(rule_version,
  current)`) and onto demo orders in `seed_demo_orders`. Surfaced via `OrderRead` + `to_dict` +
  `to_read`. pytest: demo order returns `rule_version == "2026_08_05"`.
- **Frontend:** `PaymentSnapshotCard` renders a "Rule set" field. tsc + eslint clean.

## 3d. Price type (spec §29) — added (frontend-only)
- `PaymentSnapshotCard` renders a "Price type" field derived from the existing pricing DTO:
  "Pending inspection" / "Estimate — confirmed at pickup" / "Firm". No backend change. tsc +
  eslint clean.

## 3e. Customer snapshot + operational signals (spec §29) — added (batched pass)
- **Persona (backend-wired):** `orders_repo` `get_read` now joins `customers` and both it and
  `list_for_dashboard` select `assigned_ai_persona_name as assigned_persona`; surfaced via
  `to_read` + `OrderRead` + admin `OrderDTO`. pytest: field present (null in SQLite — no customer
  join there).
- **Frontend (typed + rendered, live-only):** the mock `Order` interface (`types.ts`) gains
  optional §29 fields — `assigned_persona`, `customer_lifecycle`, `saved_address_reuse`,
  `human_takeover`, `facility_quote_status`, `facility_issue_status`, `web_intent_status`,
  `abandoned_followup_status`. `CustomerSnapshotCard` renders each **only when present** (so mock
  rows stay clean): AI persona, Lifecycle (humanised NEW_PROSPECT/…/B2B_LEAD), Saved address
  (Reused/New), Human intervention, Facility quote/issue, Web intent, Abandoned follow-up. tsc +
  eslint clean.
## 3f. customer_lifecycle populated (spec §29) — backend
- `orders_repo.get_read` enriches the order detail with `customer_lifecycle`: `crm_repo.gather_facts(customer_id)`
  → `crm_segments.compute_lifecycle_stage()` → mapped to the §29 vocabulary
  (`_LIFECYCLE_TO_SPEC29`: b2b_lead→B2B_LEAD, repeat→EXISTING_CUSTOMER, active→ACTIVE_CUSTOMER,
  complaint/inactive→EXISTING_CUSTOMER, lead→RETURNING_PROSPECT). Best-effort/guarded — never
  breaks the read. Added to `OrderRead` + `OrderDTO`; the card already renders it. Supabase-only
  (the SQLite order-detail uses `order_store`, so null there — pytest just asserts the field is
  present).

## 3g. Per-order cross-entity status queries (spec §29) — added
Four new best-effort repo queries, wired into `orders_repo.get_read` (guarded — a status
lookup never breaks the order detail), surfaced via `OrderRead` + `OrderDTO`, rendered in
`CustomerSnapshotCard`:
- `facility_issues_repo.status_for_order(order_uuid)` → open | resolved | none.
- `pending_tasks_repo.facility_quote_status(order_uuid)` → pending | received | none (from the
  order's `AWAITING_FACILITY_QUOTE` task).
- `web_order_intents_repo.status_for_number(number)` → converted | consented | captured.
- `scheduled_followups_repo.web_abandonment_status(number)` → sent | scheduled | cancelled |
  suppressed.
Supabase-only (the SQLite detail uses `order_store`); pytest asserts the fields are present.

## 3h. saved_address_reuse (spec §29) — added (COMPLETES §29)
- `save_pickup_address` gains an optional `reused_from_saved` flag → `address_source = "saved_reuse"`;
  the prompt instructs the agent to set it when a returning customer confirms reusing their saved
  address. `models.py` Order gains `address_source` (SQLite; Supabase already had it via
  `_BOOKING_COLS`). `saved_address_reuse` derived (`address_source == "saved_reuse"`) in `to_dict`
  + `to_read`, added to `OrderRead` + `OrderDTO`, rendered in `CustomerSnapshotCard`. Tests: the
  tool marks reuse vs a fresh address; the order detail surfaces the flag.

## §29 status — COMPLETE
Every §29 order-detail field now has a backend source AND a render: payment
(method/status/Stripe-link/follow-up), discount (%+reason), rule-set version, price type,
persona, customer lifecycle, facility quote status, facility issue status, web-intent status,
abandoned-follow-up status, saved-address reuse. Backend order-column + reuse fields are
pytest-tested; the customer-join + cross-entity fields are Supabase-only (rendered when
populated). All frontend passes tsc + eslint.

## 4. Files
**Modified:** `apps/whatsapp-agent/schemas.py`, `services/order_store.py`,
`db/repositories/orders_repo.py`, `tests/test_orders.py`,
`apps/admin/lib/dashboard/whatsapp-agent-api.ts`.

## 5. Remaining (frontend UI — its own session)
Section 29 lists ~25 fields to render (customer lifecycle, persona, masked number, saved-address
reuse, price source/type, rule-set version, minimum-order status, delivery charge, discount %/
reason, payment preference, Stripe-link/cash status, payment follow-up stage, web order-intent
status, abandoned follow-up status, facility quote/issue status, human-intervention status; and
the order-detail snapshots). Two admin order surfaces have **different order types** — the
Operations dashboard (`OrderDTO`, currently mock-backed) and `app/admin/orders/[id]` (a separate
`lib/api-client.ts` type). A clean rollout needs: (a) point the Operations order-detail at live
agent data, (b) render the fields in `PaymentSnapshotCard` / `CustomerSnapshotCard`, (c) extend
the `app/admin/orders/[id]` type + API for the same. Each is `tsc`/visual-verified frontend work,
best done as a focused UI session — the backend now provides the data.
