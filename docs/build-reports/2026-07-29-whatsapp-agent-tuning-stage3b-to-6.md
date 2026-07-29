# Build Report — WhatsApp Operations Agent Tuning, Stages 3b–6

**Date:** 2026-07-29
**Type:** Backend — tools, routing, privacy, regression (mock-first)
**Program:** WhatsApp Operations Agent tuning. Covers **Stages 3b, 4, 5, 6** (Stages 1–3 in
their own reports; Stage 7 = this + weekly/presentation docs).

## Objective
Complete the agent-tuning program: expose the min-order-fee + express tools, add
route-to-human specialist categories, add adversarial privacy tests, and encode the §12
scenarios as a regression suite + a runnable replay harness. All mock-first, no live calls.

## Stage 3b — min-order fee + Express tool (§2.3 / §2.4)
- `get_order_summary` now returns the delivery charge (`services/fulfilment`): `delivery_free`,
  `delivery_fee_aed` (flat 8 below AED 50), `free_delivery_min_aed`, `order_grand_total_aed`.
- New tool **`quote_express`** (`services/delivery.express_quote`): eligibility, +50% surcharge,
  `express_total`, and `requires_facility_check` when the request is after the 3 PM cut-off
  (post-cut-off is **not** auto-rejected — the agent confirms capacity + offers the standard 24h).
- Prompt updated for both. *(Deferred: live facility-cost lookup — the floor's cost basis is a
  founder open item; see below.)*

## Stage 4 — route-to-specialist (§2.8)
- New `config/specialty_routing.json` + `services/specialty_routing.py` (pure classifier) for
  **HOME_CLEANING** (villa/home/deep cleaning), **WEDDING_DRESS**, **LUXURY_BESPOKE** (couture/
  exotic leather/re-dye/restoration). Config-driven terms + acknowledgements + capture fields.
- `services/service_resolution` gains `ServiceKind.ROUTE`, checked **before** catalogue aliasing
  so "wedding dress" routes to a specialist instead of being quoted as Clean & Press.
- New tool **`route_to_specialist`**: captures structured details, logs an
  `AWAITING_OPERATIONS_RESPONSE` follow-up task, and returns a specialist acknowledgement. The
  agent never quotes these. B2B stays with `services/b2b.py` + the escalation rules.

## Stage 5 — privacy firewall, adversarial (§7)
- New `tests/test_privacy_firewall.py`: injects a customer phone / email / full address into every
  outward + model-facing surface and asserts they NEVER appear in facility/driver notifications,
  the model-facing `workflow_state_block` (only `pickup_address_present` + area), or the
  `get_customer_record` tool output. Plus `mask_pii` unit coverage.

## Stage 6 — §12 regression scenarios + replay harness (§11/§12)
- New `tests/test_scenarios_regression.py`: one test per §12 scenario (1–14), driving the real
  engines (pricing/negotiation/delivery/routing/complaints/privacy) + the assembled system prompt.
- New `scripts/replay_scenarios.py`: a runnable mock-mode harness printing PASS/FAIL per scenario
  (exit non-zero on any failure). **14/14 pass.**
- Added the promo-suppression rule to the prompt (§2.12.9/§6.4: never send review/promo while a
  complaint is open).

## Files created
- `config/specialty_routing.json`, `services/specialty_routing.py`
- `scripts/replay_scenarios.py`
- `tests/test_stage3b_tools.py`, `tests/test_specialty_routing.py`, `tests/test_privacy_firewall.py`,
  `tests/test_scenarios_regression.py`

## Files modified
- `agents/whatsapp_agent/booking_tools.py` (get_order_summary delivery fee; `quote_express`,
  `route_to_specialist` tools + handlers; ROUTE branch in save_service_selection; prompt updates)
- `services/service_resolution.py` (`ServiceKind.ROUTE`)
- `tests/test_service_resolution.py` (wedding-dress now routes)

## API / DB / UI / integrations
- **API:** none. **DB:** no migration (routing uses the existing pending-tasks table). **UI:** none.
- **Agent behaviour:** delivery fee shown in summaries; Express same-day path; villa/wedding/luxury
  routed to specialists; promo suppression during complaints.

## Tests run / results (honest)
```
pytest tests/test_stage3b_tools.py tests/test_specialty_routing.py tests/test_privacy_firewall.py \
       tests/test_scenarios_regression.py -q            # 5 + 17 + 5 + 15 = 42 passed
python -m scripts.replay_scenarios                       # 14/14 scenarios passed
# Consolidated program regression (17 suites): 286 passed
ruff check <all program files>                           # All checks passed
```
Full suite not run (README: large; targeted runs). No live WhatsApp/LLM/Stripe/secrets touched.

## Known limitations / founder open items
- **Facility-floor cost basis** (Stage 3): the floor needs a facility COST per order; the model
  (per-unit rate × qty? a facility order-cost?) is a **founder decision** — until confirmed,
  `_facility_cost_for_order` returns None and deep haggling safely escalates to a human.
- `agent_name` placeholder + Qatar (QAR) price list remain open (spec §13).
- Ghost-timer auto-advance deferred (needs a scheduler); the negotiation tool advances per-haggle.
- FSM fallback path quotes full price (no negotiation tool) — acceptable; Claude orchestration is default.
- Re-seed `delivery_sla_rules` (carpet 2–5d / express meta) before live use (JSON is the hot path).

## Next recommended step
Founder to (1) set `agent_name`, (2) confirm the facility-floor cost basis + provide the Qatar
price list, then wire the live facility-cost lookup and re-seed the SLA table. After that,
live-WhatsApp readiness review.
