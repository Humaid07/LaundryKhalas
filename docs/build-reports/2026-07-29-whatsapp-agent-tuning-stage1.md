# Build Report — WhatsApp Operations Agent Tuning, Stage 1 (Rules & Config Layer)

**Date:** 2026-07-29
**Type:** Backend — config + pure services + unit tests (mock-first, additive)
**Program:** WhatsApp Operations Agent tuning against founder-approved spec (§1–§13) + 493-chat intelligence. Staged build; this is **Stage 1 of 7**.

## Objective
Encode the founder-approved business rules (spec §2) and the negotiation engine (spec §3)
as **data/config + pure, deterministic services**, not hardcoded prose — so rules can be
tuned without touching agent code. Stage 1 is deliberately **additive and non-breaking**:
new modules land fully unit-tested alongside the existing system; wiring them into the
agent prompt/tools and retiring the automatic discount happen atomically in later stages.

## Founder decisions applied (this session)
1. **Discount model = negotiation-only.** The automatic 15%-over-AED-100 discount will be
   retired; the agent quotes the full website price and the §3 ladder fires only on
   haggling. *(Config for the new engine is built now; the removal of the auto-discount is
   sequenced into Stage 3 so the change is atomic with the negotiation wiring.)*
2. **QAR = plumbing now, price list later.** Currency-by-country plumbing is built; QAR
   pricing stays unconfigured (`pricing_configured=false`) → QAR quotes route to a human
   until a Qatar price list is provided. No QAR numbers were invented.

## What was built

### Negotiation engine (spec §3) — the centrepiece
- **`config/negotiation.json`** — ladder (low tier <100 → 10%→20%; high tier ≥100 →
  15%→25%), `ghost_timeout_seconds=300` (5 min), `max_concession_fraction=0.75`,
  `itemisation_required_for_floor=true`, per-market (AE/QA).
- **`services/negotiation.py`** (pure, Decimal):
  - `ladder_offer(subtotal, step)` — each rung discounts the **original** subtotal (never
    stacks); flags `is_standard_max` and `exhausted`.
  - `is_ghosted(seconds)` — strictly `> 300s`.
  - `facility_floor(discounted_price, facility_cost, itemised=…)` — implements
    `floor = discounted − 0.75 × (discounted − facility_cost)` with guards: itemisation
    required, non-positive/missing cost blocked, `no_room` when cost ≥ price. The raw
    facility cost is **never** surfaced — only the floor price is returned to the model
    (CLAUDE.md §7). Both results expose `to_snapshot()` for the audit log (spec §3.4).

### Minimum order + delivery charge (spec §2.3)
- **`config/fulfilment_charges.json`** + **`services/fulfilment.py`** — free pickup/delivery
  at/above AED 50; flat AED 8 below; currency-aware; `to_snapshot()`.

### Currency / market plumbing (spec §8)
- **`config/markets.json`** + **`services/market.py`** — resolve market from phone prefix
  (971→AE/AED, 974→QA/QAR), `format_price()` never mixes currencies, `pricing_configured`
  gates QAR → human. Unknown prefix falls back to default market (no crash).

### Express surcharge + 3 PM cut-off (spec §2.4)
- **`config/delivery_sla.json`** meta: `express_surcharge_pct=0.5`, `express_cutoff_local="15:00"`.
- **`services/delivery.py`** (additive): `express_surcharge_pct()`, `is_after_express_cutoff()`,
  `apply_express_surcharge()`, `express_quote()` → +50% total and `requires_facility_check`
  when a same-day request arrives after 3 PM (post-cut-off is **not** auto-rejected, spec §2.4).

### Turnaround correction (spec §2.5)
- Carpet SLA changed from 3–4 days (72–96h) to **2–5 days** (48–120h) per founder spec.

### Persona config (spec §1/§13)
- **`config/persona.json`** — single `agent_name` (placeholder, **OPEN ITEM for founder**),
  `reveal_ai=false`, languages (en/ar native), voice rules. Consumed in Stage 2 (not wired yet).

## Files created
- `apps/whatsapp-agent/config/negotiation.json`
- `apps/whatsapp-agent/config/fulfilment_charges.json`
- `apps/whatsapp-agent/config/markets.json`
- `apps/whatsapp-agent/config/persona.json`
- `apps/whatsapp-agent/services/negotiation.py`
- `apps/whatsapp-agent/services/fulfilment.py`
- `apps/whatsapp-agent/services/market.py`
- `apps/whatsapp-agent/tests/test_negotiation.py`
- `apps/whatsapp-agent/tests/test_fulfilment_charges.py`
- `apps/whatsapp-agent/tests/test_market.py`
- `apps/whatsapp-agent/tests/test_express_surcharge.py`

## Files modified
- `apps/whatsapp-agent/config/delivery_sla.json` (express surcharge/cut-off meta; carpet 2–5 days)
- `apps/whatsapp-agent/services/delivery.py` (additive express-surcharge/cut-off helpers)
- `apps/whatsapp-agent/tests/test_delivery_sla.py` (carpet assertions 72–96 → 48–120)

## API / DB / UI / agent-behaviour changes
- **API endpoints:** none.
- **DB tables/models:** none. (`delivery_sla.json` is DB-seeded via
  `scripts/seed_delivery_sla.py`; re-seeding is a later, separate step — not run this stage.)
- **UI:** none.
- **Agent behaviour:** **none yet** — Stage 1 modules are not imported by the agent/prompt/
  tools. Behaviour changes land in Stages 2–4.

## What is mock-only / live / deferred
- **Mock-only:** everything here is pure config + logic under `LLM_PROVIDER=mock` test env.
- **Live:** nothing enabled. No live WhatsApp/LLM/Stripe touched.
- **Deferred to later stages:** wiring the engines into the system prompt (Stage 2) and
  tools + atomic removal of the auto-discount (Stage 3); villa/wedding/couture routing
  (Stage 4); dedicated privacy tests (Stage 5); §12 regression scenarios + replay harness
  (Stage 6); weekly report + presentation notes (consolidated at program end to avoid churn).

## Tests run
```
cd apps/whatsapp-agent
./.venv/Scripts/python.exe -m pytest tests/test_negotiation.py tests/test_fulfilment_charges.py \
  tests/test_market.py tests/test_express_surcharge.py tests/test_delivery_sla.py -q
./.venv/Scripts/python.exe -m ruff check services/{negotiation,fulfilment,market,delivery}.py tests/test_negotiation.py …
./.venv/Scripts/python.exe -m pytest tests/test_order_discount.py tests/test_final_pricing.py tests/test_catalogue_pricing.py -q
```
## Test results (honest)
- New + touched SLA suite: **81 passed**.
- ruff on all new/changed modules: **All checks passed**.
- Pricing/discount regression (auto-discount untouched this stage): **104 passed**.
- Full suite NOT run this session (README: large; run targeted files when iterating).

## Acceptance criteria
1. ✅ Negotiation ladder, ghost timer, floor formula, itemisation guard encoded as config +
   pure service; founder's worked example (60 → 20% → 48; cost 30 → floor **34.50**) is a test.
2. ✅ Min-order/delivery (≥50 free / <50 → 8), express +50% & 3 PM cut-off, AED/QAR plumbing,
   carpet 2–5 days all config-driven.
3. ✅ Raw facility cost never returned to the model (only the floor price); audit snapshot
   keeps the cost for the log only.
4. ✅ Additive & non-breaking — existing pricing/discount tests still green.
5. ✅ No live external calls; no secrets; no invented QAR prices.

## Known limitations / next steps
- Auto-discount still active until Stage 3 (intentional — atomic swap with negotiation wiring).
  Interim, the agent's discount behaviour is unchanged.
- `delivery_sla_rules` DB table not re-seeded with carpet 2–5 days / express meta yet (JSON is
  the hot-path source; re-seed is a deliberate later step before any live use).
- `agent_name` is a **placeholder** — founder must set it (spec §13).
- **Next: Stage 2** — assemble the agent system prompt (persona, flow §2.12, AED/QAR overlay,
  Arabic) pulling live values from this config.
