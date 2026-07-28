# Build Report — Customer-tier engine + production-spec coverage validation

**Date:** 2026-07-28

## Context
The task re-stated the full production spec. A coverage audit against the just-
committed tree (`f83167f`) found the great majority already implemented; this
report validates that (ran the relevant suites) and closes the cleanest genuine
gap — the backend customer-tier engine — without touching the files a concurrent
session is editing.

## Coverage map (spec area → status in the committed tree)
- Adaptive per-conversation aggregation → **DONE** (`services/message_completeness`, `WHATSAPP_DEBOUNCE_*_MS`).
- Service persistence + unsupported service ("haircut") → **DONE** (`services/service_resolution`).
- Post-confirmation silence / terminal turn → **DONE** (`services/post_confirmation`).
- Refund → human intervention (durable pause, idempotent) → **DONE**.
- Abuse/threat → human intervention → **DONE** (`services/abuse_classification`, `human_intervention`, migration `000028`).
- Timezone pickup date/time + slot filtering + lead time → **DONE** (`services/clock`/`pickup_datetime`/`pickup_availability`).
- VAT-inclusive pricing, no ×1.05 → **DONE**.
- Discount precedence + AED 600→480 (measured estimate) → **DONE** (`calculate_applicable_order_discount`).
- Facility auto-assign + rates/margin/geo model → **DONE** (`facility_pricing`, `facility_routing`).
- Duplicate/idempotency (turn locks + outbound key) → **DONE**.
- **Customer-tier engine (New/Repeat/Bronze/Silver/Gold)** → **DONE THIS PASS** (below).
- Country/market config layer, website→DB catalogue sync, luxury-item image analysis,
  price-objection→nearby-facility routing wired into the agent, and the human-intervention
  **dashboard UI** → **GENUINELY NOT BUILT** (each a self-contained subsystem; see limitations).

## What was implemented (customer-tier engine)
Extended the existing deterministic CRM engine (not a new parallel system):
- `config/crm_segments.json` → new `customer_tiers` block (`rule_version` + ordered
  tier thresholds). **Configurable, never hardcoded in the prompt.**
- `services/crm_segments.py` → `compute_customer_tier(facts, config)` +
  `customer_tier_rule_version(config)`; `customer_tier` + `customer_tier_rule_version`
  added to `CrmResult`/`as_dict()` and `evaluate()`.
- Rules: **NEW** when no legitimate completed order; else the highest tier whose
  minimum completed-order count **or** minimum lifetime completed value is met
  (Gold > Silver > Bronze), else **REPEAT**. Only legitimate completed orders count
  (the repo already excludes drafts/cancelled/refunded/test when gathering
  `confirmed_order_count`/`lifetime_value`). Decimal-safe, deterministic, idempotent.
- **The LLM never assigns the tier** — it is backend-computed only.

## Files changed
`services/crm_segments.py`, `config/crm_segments.json`; new `tests/test_customer_tiers.py`.
No migration (tier is computed on demand from existing aggregates; `crm_repo` persists
explicit named columns, so the added result fields don't affect persistence).

## Tests + results
- `test_customer_tiers.py` — **15 passed**: NEW/REPEAT/Bronze/Silver/Gold thresholds
  (by count and by value), highest-tier-wins, idempotency, per-market configurability
  (rule version), and NEW-never-tiered-by-value-alone. ruff clean.
- Regression + committed-system validation (file-by-file to avoid the known
  cross-file demo-seed fixture flake): `crm_segments` 17, `service_persistence` 10,
  `service_resolution` 9, `post_confirmation` 9, `human_intervention` 7,
  `abuse_classification` 18, `pickup_scheduling` 31, `refund_intervention` 18,
  `message_completeness` 29, `outbound_idempotency` 5 — **all green**.

## Manual verification
`compute_customer_tier(CustomerFacts(confirmed_order_count=20, lifetime_value=3000))`
→ `REPEAT_GOLD`; `evaluate(...).as_dict()["customer_tier"]` surfaces it for any
dashboard/API consumer. Change `config/crm_segments.json` `customer_tiers` to retune
per market without code changes.

## Known limitations / genuinely deferred (each needs its own focused slice)
- **Tier persistence + history snapshots + dashboard display** — the engine is done;
  persisting a `customer_tier` column + a tier-history table (migration) and the admin
  UI are the follow-up (recompute on completed-order/refund/cancellation change, NOT on
  every message).
- **Country/market config layer** — currently UAE/AED is the single market; a
  `markets` config (code/currency/timezone/pricing URL/catalogue/facilities/radii/rules)
  is not yet abstracted.
- **Website→DB catalogue sync** (parse/version/publish atomically, preserve prior on
  failure) — not built; the runtime already reads the DB catalogue (no live scraping).
- **Luxury-item image analysis** (candidate brand/model/condition, confidence-aware,
  no authenticity/value claims) + full **bespoke quotation workflow** — not built.
- **Price-objection → nearby-facility routing wired into the WhatsApp agent** — the
  facility pricing/margin/geo backend exists (`facility_pricing`) but is not yet invoked
  from the live price-objection conversational flow.
- **Human-intervention dashboard UI** — backend (`api/human_intervention.py` + repo)
  exists; the admin Next.js queue/claim/reply UI is a separate app build.
- These were **not** attempted here to avoid clobbering the concurrent session's
  in-flight edits to the shared hot files and the separate dashboard app.
