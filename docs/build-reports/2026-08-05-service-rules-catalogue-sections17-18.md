# Build Report — Service-Rule Registry + Catalogue Corrections (Sections 17–18)

**Date:** 2026-08-05
**Status:** Section 17 registry + Section 18 catalogue corrections implemented; full-suite
verification in progress (appended). UNCOMMITTED.

## 1. Objective
Sections 17 (centralized service-rule registry) and 18 (approved baseline catalogue). An
audit found Clean&Press, Press Only, Shoes, Bags, Toys, Bedding, Carpets already matched the
spec exactly (prior "real price list" work). This increment fixes the three concrete Section-18
discrepancies and adds the Section-17 rule registry.

## 2. Catalogue corrections (Section 18)
- **Sole replacement — AED 550 removed.** Spec §18 (Restoration): *"Do not use the previous
  AED 550 sole-replacement price… Create a facility quotation."* `RESTORATION_SOLE_REPLACEMENT`
  is now `pricing_type: INSPECTION_REQUIRED` with no price → resolves to a facility quote
  ("Priced after inspection"), never quoting 550.
- **Curtain minimum charge AED 50 added.** Spec §18 (Curtains): *"Minimum curtain charge: AED
  50."* Added `minimum_charge: 50` to `HOME_CARE_CURTAIN_SQM` + **engine support**: a measured
  line never falls below its `minimum_charge` (`services/pricing._line_for`;
  `services/catalogue._normalise_item` now carries the field). 2 sqm → floored to AED 50; 4 sqm
  → AED 80 unchanged.
- **Cushion Cover — Large (AED 20) added.** Spec §18 (Bedding) lists it; it was missing.

## 3. Service-rule registry (Section 17)
- **`services/service_rules.py`** — `resolve_rule(item_code, market)` derives the §17 rule over
  the published catalogue (the catalogue stays the source of truth):
  - `pricing_mode` ∈ EXACT / FROM / RANGE / FACILITY_QUOTE / MEASURED / WEIGHT_CONFIRMED /
    B2B_SALES_QUOTE (derived from `pricing_type` + flags).
  - Policies: `photo_required` (bags/restoration/designer/leather/wedding),
    `inspection_required`, `facility_quote_required`, `express_eligible` (Wash&Fold / Clean&Press
    / Press Only only, §19), `discount_eligible` (firm/known totals only, §15.6),
    `specialist_required`, `measurement_required`.
  - Every rule stamps `rule_version` = `WHATSAPP_SERVICE_RULESET_VERSION` (2026_08_05).

## 4. Files
**Modified:** `config/laundry_catalogue.json` (3 corrections), `services/catalogue.py`
(`minimum_charge` field), `services/pricing.py` (minimum-charge on measured lines),
`tests/test_catalogue_pricing.py`.
**Created:** `services/service_rules.py`, `tests/test_service_rules.py`.
**Migrations:** none (config-driven).

## 5. Tests
- `test_catalogue_pricing.py` — sole-replacement facility-quote, cushion-large 20, curtain
  50-minimum (small floored, large unchanged). 123 passed in the pricing subset.
- `test_service_rules.py` — 7 tests: exact/from/measured/weight-confirmed/facility-quote modes,
  express + discount eligibility, photo/facility policies, rule_version, unknown → None.
- Full-suite regression: result appended.

## 6. Audit note — already-aligned vs remaining
- **Aligned to spec §18:** Clean&Press, Press Only, Shoes, Bags, Toys, Bedding (bar the added
  cushion-large), Carpets, Wash&Fold (corrected earlier in Phase 1).
- **Remaining (larger, spec §18):** the detailed **Alterations** price matrix (trouser
  shortening AED 40 with pushback/quantity tiers, sleeve/waist/zip/button, etc.) is currently a
  single `ALTERATIONS_GENERAL` "from AED 30" item resolved via the repair classifier + prompt;
  encoding the full matrix + B2B sales-quote flow are separate follow-ups. Wedding-dress /
  leather ranges are handled via the From/facility-quote + photo policies.

## 7. Alterations price matrix (§18) — added
- **`config/alterations.json`** — every listed alteration type with base / pushback (haggle) /
  quantity-tier prices + thresholds: trouser-shorten (40 / 35 / 30 at 6+), dress-shorten
  (45 / 40 / 35 at 2+), sleeve-shorten shirt (35) vs jacket (65), waist reduce (40 / 35 / 30)
  and expand (45 / 40 / 35), loosening (35), zip replacement (small 40 / 30, long 60 / 50 by
  who supplies the zip), button (10 each). Generic/unlisted (basic hemming, minor tear,
  tightening, lining repair) → facility quotation, no invented price.
- **`services/alterations.py`** — `resolve_alteration(text, quantity, pushback)`: longest-alias
  match → the specific type + tiered price; unlisted keywords → `facility_quote` +
  `FACILITY_QUOTE_REPLY` ("Let me confirm the price for that and get back to you."). Stamps
  `rule_version`.
- **`tests/test_alterations.py`** — 13 tests across every tier + the facility-quote fallback.

## 8. Alterations wired into the agent quote path — added
- **`lookup_alteration_price`** grounding tool (`agents/whatsapp_agent/llm_tools.py`) —
  `execute_tool` dispatches to `alterations.resolve_alteration`, returning the exact tiered
  price (`match: ok`) or a facility quotation (`match: facility_quote` + the approved reply).
  Registered in `booking_tools._GROUNDING_TOOL_NAMES`.
- **Prompt** updated: the agent now calls `lookup_alteration_price` for the EXACT alteration
  price (base/pushback/quantity tiers) instead of quoting the coarse "alterations start from
  AED 30"; unlisted alterations return priced-after-inspection. Grounding rule lists the new
  tool. Two prompt-assertion fixtures updated to the new wording.
- Tests: tool returns exact price (6+ tier → AED 30 × 6 = 180), routes unlisted → facility
  quote, requires a description.

## 9. Next
Encode the B2B sales-quote flow (§18 Commercial); optionally stamp the resolved `service_rules`
rule + version onto each persisted quote snapshot.
