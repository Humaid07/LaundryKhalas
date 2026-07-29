# Build Report — Facility-Cost Engine + Negotiation Floor Wiring

**Date:** 2026-07-29
**Type:** Backend — facility-cost derivation (mock-first)
**Follows:** WhatsApp agent tuning program + QAR pricing. Closes founder open item #2
(the facility-floor cost basis).

## Objective
Implement the founder's facility-cost model so the negotiation floor (spec §3.2) is anchored on
a REAL backend-derived facility cost — never a Claude guess — and so that a missing rate produces a
durable facility-quotation request + a pending price rather than an arbitrary number.

## Founder model (2026-07-29) implemented
- **Standard catalogue services** → the selected facility's ACTIVE service-rate record, billed by
  the correct pricing unit × quantity / weight / item-count / square-metre.
- **Bespoke / restoration / luxury / inspection** → the selected valid facility QUOTATION.
- **Facility minimum charge** + **operational fees** applied where configured.
- The central **margin rule** produces the customer quotation; the §3.2 floor protects margin above
  cost as the **minimum selling price**.
- **Claude never invents** the facility cost or margin.
- **No valid rate/quotation** → durable facility-quotation request + price **pending** (never arbitrary).
- **Human intervention only** when: no facility responds in the escalation window; a quote needs
  commercial approval; the customer keeps pushing **below the minimum selling price**; or cost data is
  missing/conflicting.
- Rate provision: **both** — stored per-service rates (fed via the command centre) for standard
  services + facility-submitted quotations for bespoke.

## What was built
- **`services/facility_cost.py`** (pure): `compute_facility_cost(lines, rates, quotations,
  min_charge, operational_fees)` → `FacilityCostResult` (cost, complete, subtotal, min-charge-applied,
  operational-fees, unpriced_lines). `billable_quantity()` picks measure vs count by pricing type;
  `line_needs_quote()` flags bespoke/inspection/`STARTING_FROM`. Any unpriced line ⇒ `complete=False`,
  `facility_cost=None` (no arbitrary number). Decimal via `services.money`.
- **`agents/whatsapp_agent/booking_tools.py`**:
  - `_facility_cost_for_order()` now fetches the lowest active facility rate per service
    (`facility_pricing_repo.candidates_for_service` + `facility_pricing.pick_lowest`), builds the
    line/rate maps from the catalogue, and calls the engine — fully guarded (any DB/offline failure or
    an incomplete cost ⇒ None ⇒ pending). Cost is logged, never surfaced (CLAUDE.md §7).
  - `negotiate_order_price` now splits the post-ladder path: **no facility cost** ⇒ `action:"pending"`
    + a durable `AWAITING_FACILITY_QUOTE` task; **below the floor** ⇒ `action:"escalate"` (human).
  - Prompt updated: the negotiation tool's `pending` action + the four human-intervention triggers.

## Files created
- `apps/whatsapp-agent/services/facility_cost.py`, `apps/whatsapp-agent/tests/test_facility_cost.py`

## Files modified
- `agents/whatsapp_agent/booking_tools.py` (`_facility_cost_for_order`, negotiate pending/escalate,
  prompt), `tests/test_booking_tools.py` (carpet negotiate → pending path)

## API / DB / UI / integrations
- **API/UI:** none. **DB:** no migration — uses existing `facility_rates` / `margin_rules`.
  Facility **minimum-charge**, **operational-fee**, and **facility-quotation** tables do NOT exist yet
  (the command centre is still being wired to feed rates); the engine accepts them as inputs and
  defaults them off until the schema + dashboard provide them.

## Tests run / results (honest)
- `tests/test_facility_cost.py` (8) — per-item, per-kg, per-sqm, min-charge, operational fees, bespoke
  quotation, incomplete→no-number, mixed order.
- `tests/test_booking_tools.py` negotiation: floor reached (via a provided cost) → escalate below it;
  no cost → `pending` + facility-quote task.
- Broad program regression + replay (see run). ruff clean on changed files. No live calls; the facility
  cost is never shown to the model/customer.

## Known limitations / next
- **Facility rates are per `service_code` (category)**, so a category's per-unit rate is applied to
  each of its lines; per-ITEM facility rates (finer granularity) + the min-charge/operational-fee/
  quotation tables are the next schema+dashboard step. The engine already supports them as inputs.
- Until the command centre feeds rates, deep haggling yields `pending` (a facility-quote request) —
  exactly the founder's intended behaviour, no arbitrary price.
- Remaining founder item: set `agent_name`.
