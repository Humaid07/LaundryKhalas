# WhatsApp Operations Agent — Spec Gap-Close (A–F)

- **Date:** 2026-07-31
- **Author:** Engineering (Claude Code, dev@laundrykhalas.com)
- **Status:** Approved design → implementation plan next
- **Scope root:** `apps/whatsapp-agent/`
- **Mode:** Mock-first. No live LLM / WhatsApp / Stripe. Migrations to dev/test Supabase only.

## 1. Background

The WhatsApp Operations Agent spec (493-conversation intelligence build) was re-issued in
full. A grounded inventory of `apps/whatsapp-agent/` against the spec's 18 areas found **11
DONE** (negotiation engine, privacy firewall, escalation/takeover, VAT-inclusive pricing,
min-order/delivery, express surcharge + 3PM cutoff, complaints, market/currency detection,
coverage, sell-vs-route map, and all 14 §12 regression scenarios) and **7 PARTIAL/MISSING**.

Founder decision: **gap-close against spec**. This document specifies the six gap items
(A–F) approved for this pass. Two areas (persona single-name vs per-customer, and a general
pre-send approval queue + driver-availability tool) are **deferred as open founder
decisions** and documented in §9 — not built.

## 2. Goals / Non-goals

**Goals**
- Close the six functional/data gaps A–F below, mock-first, fully tested.
- Keep all facility cost/margin data server-side and out of any customer/facility/model-
  facing output (privacy firewall, CLAUDE.md §7).
- Preserve the deterministic, "never invent a value" contract of the booking FSM and the
  pricing/SLA engines.

**Non-goals**
- No live Stripe integration or real payment-link minting (deferred).
- No persona-naming change (deferred, founder decision G).
- No general pre-send human-approval queue and no real driver-availability tool (deferred,
  founder decision H).
- No refactor beyond what these items require.

## 3. Item A — Facility rate card (Appendix A), per-item

**Problem.** `facility_cost.compute_facility_cost` keys facility rates by **catalogue
category** (`WASH_FOLD`, `CLEAN_PRESS`, `SHOE_CARE`, `BAG_CARE`). Seed migration
`20260728_000027_facility_rates_margin.sql` covers only those five categories (labelled
MOCK) and omits `HOME_CARE`, `SOFT_TOY`, `ALTERATIONS`, `RESTORATION`. Consequences:
1. Floor-negotiation on Home & Care / Alterations / Soft Toy / Restoration orders returns
   `no_facility_cost` → escalate, instead of computing a real floor.
2. One flat rate per category means thin-margin items (shirt 7 vs abaya 8 vs kandura 7,
   carpet 15/sqm vs wool 22/sqm) all cost the same — the spec §3.5 explicitly requires
   **per-item** costing so a whole-order 25% discount cannot silently dip below cost on a
   thin line.

**Decision (approved): A2 — per-item rate card, keyed by `item_code` with category
fallback.**

**Data model.** New migration `20260731_000036_facility_item_rates.sql` (dev/test only,
additive, idempotent):
- New table `facility_item_rates (id, facility_id, item_code, rate numeric(12,2),
  currency default 'AED', active bool, valid_from, valid_to, created_at, updated_at,
  unique(facility_id, item_code))`, RLS enabled (deny; service role bypasses), `set_updated_at`
  trigger, index on `item_code`. Mirrors `facility_rates` shape but item-grained.
- Seed the full Appendix A card for the two existing MOCK facilities
  (`FAC-DXB-MARINA`, `FAC-AUH-CENTRAL`), mapping each Appendix-A line to its catalogue
  `item_code`. Rows the catalogue has no item for are skipped (documented in the migration
  comment). Per-facility variance kept minimal (Appendix A is "one facility's rates"; the
  second facility seeded at the same values or a small delta, MOCK).
- Extend `facility_services` seed so both facilities `offer` the added categories
  (`HOME_CARE`, `SOFT_TOY`, `ALTERATIONS`, `RESTORATION`) — otherwise availability filtering
  excludes them.
- Keep the existing category-level `facility_rates` rows as the **fallback** tier.

**Rate-card → item_code mapping.** A build-time step maps the Appendix-A names (Shirt, Abaya,
Kandura, Carpet Regular/sqm, Boots, Backpack, "Jeans length cut", …) to catalogue
`item_code`s. The mapping is generated/verified against `config/laundry_catalogue.json`; any
Appendix-A line with no catalogue match is listed in the migration comment and left unseeded
(no invented item). Alterations rates (AED, e.g. 13.20, 17.60) map to the `ALTERATIONS`
catalogue items; where the catalogue models alterations as `STARTING_FROM`/inspection, those
lines remain quotation-based and the item-rate acts as the quotation seed.

**Lookup change (`services/facility_cost.py`).** `compute_facility_cost` gains an optional
`item_rates: dict[str, float] | None` (keyed by `item_code`). Per line the resolution order
is: **(1) valid facility quotation** (bespoke/inspection lines — unchanged) → **(2)
`item_rates[item_code]`** → **(3) `rates[service_code]`** (category fallback) → **(4)
unpriced** (order INCOMPLETE → `facility_cost=None` → pending/escalate, never a guess).
Measured lines (`PER_KG`, `PER_SQM`) still multiply the resolved rate by the measure; count
lines by quantity. Pure/deterministic; no behaviour change when `item_rates` is absent (back-
compat for existing tests).

**Caller change (`agents/whatsapp_agent/booking_tools._facility_cost_for_order`).** In
addition to the per-category `rates` map it already builds, load per-item rates for the
order's `item_code`s via a new repo method and pass them as `item_rates`. Failure/offline →
falls back to category rates, then to pending — same fail-safe as today. Facility cost is
still logged internally only and never surfaced.

**Repo (`db/repositories/facility_pricing_repo.py`).** Add
`item_rates_for_items(item_codes, market)` (or `candidates_for_item`) returning the lowest
active item-rate per `item_code` among qualified nearby facilities, mirroring the existing
`candidates_for_service` + `facility_pricing.pick_lowest` pattern.

**Privacy.** Item rates are cost data — same class as category rates. They flow only into the
backend floor math; never into `workflow_state_block`, facility handoff, or any customer/model
message. Existing `test_privacy_firewall.py` assertions continue to guard this; add an
assertion that item rates never appear in the assembled prompt/state.

## 4. Item B — Payment-method capture (mock)

**Problem.** Stripe-first / cash-fallback is prompt text only; no `payment_method` is
persisted and there is no explicit "request payment link" handoff. The spec: agent pushes
Stripe, accepts cash on reluctance, **does not mint the link itself**, and never arranges an
off-system cash side-deal with the driver.

**Design.**
- **Column:** migration adds `orders.payment_method text` with a CHECK in
  (`'unset'`,`'card'`,`'cash'`), default `'unset'`. Additive/idempotent, dev/test only. (Fold
  into the same 000036 migration or a sibling — decided in the plan.)
- **Tool:** `set_payment_preference(method)` (Claude path) validates `method ∈ {card, cash}`,
  persists it, logs an `AIActionLog`/agent-log entry. Rejects anything else.
- **Mock handoff:** `request_payment_link()` does **not** create a Stripe link. It creates the
  existing `AWAITING_PAYMENT` pending-task (the type already exists) + logs a handoff, and
  returns a message the agent uses to tell the customer a secure link will follow. Guarded so
  it is only meaningful post-confirmation / pre-dispatch.
- **Currency:** reuse `market.py` — the pending-task/handoff records the order's own currency
  (AED/QAR); no mixed-currency path.
- **Prompt:** keep the existing Stripe-first / cash-fallback / no-driver-side-deal guidance;
  it now backs onto real persistence + a real (mock) handoff instead of being aspirational.

**Explicitly deferred:** real Stripe API, link generation, payment-reflected webhook.

## 5. Item C — Alterations structured capture (mock)

**Problem.** cm-vs-inch and sample/measurements exist only as prompt instructions; no state
field or tool records them, so the cm/inch guard depends on LLM goodwill (a real error source
in the corpus).

**Design.**
- **Tool:** `record_alteration_details(item, measurement_value?, unit?, has_sample)` on the
  Claude path. **Hard validation:** if `has_sample` is false, a `measurement_value` **and** a
  `unit ∈ {cm, inch}` are required; any other unit (or a missing unit with measurements) is
  rejected with a message asking the customer to confirm cm or inch. Persists the structured
  detail via the existing `order_notes` mechanism (sanitised, PII-safe), tagged as an
  alteration spec, so it reaches the facility/tailor through the normal notes handoff.
- **Prompt:** retain the sample-or-measurements + tailor-inspection-caveat guidance; the tool
  makes cm/inch a tested gate.

**Non-goal:** no new FSM state (the deterministic FSM does not deep-handle specialty
alterations; those run through the Claude path).

## 6. Item D — Alterations turnaround fix

`config/delivery_sla.json`: `SLA_ALTERATIONS` → `min_hours: 24, max_hours: 48,
display_text: "1–2 days"` (spec §2.5 tailoring 1–2 days; currently fixed 2 days). Pure config
+ `delivery.reload_sla`. Covered by a `test_delivery_sla.py` assertion.

## 7. Item E — Stale docs reconcile

`services/market.py` module docstring and `services/delivery.py` header claim "Qatar (QAR) is
not yet priced". `markets.json` now sets QA `pricing_configured: true` with a live QA
catalogue overlay. Update both docstrings to reflect that QA is priced; no code/behaviour
change. (Also reconcile the `market_for_phone` inline note.)

## 8. Item F — Express = same-day (founder semantics)

**Founder decision:** express means **"same-day delivery when collected before the 3 PM
cutoff"**, tied to the **calendar day** — not a rigid 12-hour clock. Don't hardcode 12h.

**Design (`config/delivery_sla.json` + `services/delivery.py`).**
- Retire `express_hours: 12` from the customer-facing turnaround path. Introduce an express
  model of **same calendar day**: when the whole order is express-eligible and pickup is
  **before** `express_cutoff_local` (15:00), express turnaround display = **"same day"** and
  `estimate_delivery` targets **end-of-business on the pickup date** (a configurable
  `express_same_day_end_local`, e.g. 21:00) rather than `pickup_end + 12h`.
- Unchanged: +50% surcharge (`express_surcharge_pct: 0.5`); the 15:00 cutoff; post-cutoff is
  **not** auto-rejected — caller checks facility capacity and, if unavailable, offers the
  standard 24h window (`requires_facility_check` already models this).
- `delivery_options` / `express_quote` snapshots updated to carry a `same_day` flag and the
  "same day" display text instead of "12 hours (Express)". `express_hours()` retained only if
  a numeric fallback is still referenced; otherwise removed.
- Docstrings in `delivery.py` updated to describe the same-day model (removes the "Express =
  12h" statements).

## 9. Deferred (open founder decisions — documented, not built)

- **G. Persona naming.** Implementation deliberately uses a **persistent per-customer name**
  from an approved list (Sara/Maya/Zoya/Hanna/Sofia/Max/Ben) via `services/persona_assignment.py`,
  not the spec's single `AGENT_NAME`. Richer than spec; needs founder sign-off on which model
  to keep. No change this pass.
- **H. Pre-send approval queue + driver-availability tool.** CLAUDE.md MVP implies every agent
  reply is human-approved and driver availability is checked live. Implementation uses
  deterministic auto-reply gating (reactive takeover on abuse/refund/specialist) and models
  driver availability only as an `AWAITING_DRIVER_CONFIRMATION` pending-task, not a queryable
  tool. Architectural decision; no change this pass.

## 10. Testing

- `test_facility_cost.py`: per-item rate resolution order (quotation → item_rate → category →
  unpriced); Home&Care / Alterations orders now cost; a thin-line case proving per-item floor
  differs from the old blended-category floor; back-compat when `item_rates` omitted.
- `test_delivery_sla.py`: tailoring 1–2 days; express = same-day display + end-of-day estimate
  before cutoff; post-cutoff `requires_facility_check`; surcharge unchanged.
- `test_payment_preference.py` (new): `set_payment_preference` validates/persists card|cash,
  rejects junk; `request_payment_link` creates `AWAITING_PAYMENT` pending-task and mints no
  link.
- `test_alterations_capture.py` (new): `record_alteration_details` rejects a non-cm/inch unit
  and a measurement with no unit; accepts sample-only and cm/inch; persists to order_notes.
- `test_privacy_firewall.py`: item rates never appear in prompt/state/facility handoff.
- `test_scenarios_regression.py`: migrate S8 (payment) and S11 (alterations cm/inch) from
  prompt-string assertions toward runtime-behaviour assertions now that tools exist; S4
  express wording → "same day".
- Migrations applied + verified on dev/test Supabase via the existing asyncpg apply/verify
  script pattern; `verify no live external calls`.

## 11. Migrations summary

- `20260731_000036_*.sql` (dev/test only, additive, idempotent):
  `facility_item_rates` table + full Appendix-A per-item seed for both MOCK facilities;
  `facility_services` rows for the added categories; `orders.payment_method` column.
  (The plan may split payment_method into a sibling migration for clarity.)

## 12. Risks / notes

- **Rate-card mapping fidelity:** the value of A2 depends on mapping Appendix-A names to real
  `item_code`s accurately. Unmapped lines are left unseeded (never invented). Founder should
  confirm the Appendix-A card is current and per-facility (open item in the spec §13).
- All facility cost data is MOCK; production rate rows per real facility are a later step.
- Keep changes scoped; do not touch persona (G) or approval-queue (H).
