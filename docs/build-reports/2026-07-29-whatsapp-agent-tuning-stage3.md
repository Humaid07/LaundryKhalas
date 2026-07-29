# Build Report — WhatsApp Operations Agent Tuning, Stage 3 (Negotiation-only discount + tool)

**Date:** 2026-07-29
**Type:** Backend — pricing/discount refactor + new negotiation tool (mock-first)
**Program:** WhatsApp Operations Agent tuning. **Stage 3 of 7** (tool-gating, discount model).

## Objective
Enact the founder decision **negotiation-only**: retire the automatic 15%-over-AED-100 /
20%-over-200 discount, quote the full website price by default, and expose the §3 negotiation
ladder + facility-floor as an authority-gated tool the agent calls only when the customer
haggles. Done **without a DB migration** — negotiation state is encoded in the order's existing
discount columns. The independent min-order-fee and express-surcharge tools are deferred to a
short follow-up slice (3b) to keep this change reviewable.

## What was built

### Auto-discount retired (default) — full-price quoting
- **`settings.py`**: `auto_order_discount_enabled: bool = False` (rollback flag; the legacy
  automatic engine `services/discount.py` is preserved but off).
- **`services/pricing.py`**: `calculate_estimate()` gains `negotiated_final_total` and a single
  `_resolve_discount()` with precedence — (1) an agreed negotiated total, else (2) the legacy
  auto engine *only if re-enabled*, else (3) **no discount / full baseline price** (spec §2.1).
- **`services/booking_flow.py`**: `_pricing_updates()` / `pricing_updates_for_row()` thread
  `negotiated_final_total` so an agreed price persists as the order's final total.

### Negotiation ladder + facility-floor (§3) wired end-to-end
- **`services/negotiation.py` `plan_offer()`** (new): decides the next move from the persisted
  state — `offer_ladder` (10→20 / 15→25, each rung off the **original** subtotal, never stacks),
  `offer_floor` (`discounted − 0.75×(discounted − facility_cost)` when itemised + cost known),
  `ask_itemisation`, or `escalate`. Returns a loggable `NegotiationDecision`.
- **`agents/whatsapp_agent/booking_tools.py`**: the discount tool
  `calculate_applicable_order_discount` is **replaced by `negotiate_order_price`** (old name kept
  as a handler alias). It computes the full baseline, reads the persisted negotiation state from
  the discount columns (`discount_percentage` + `discount_rule_code` ∈ {`NEGOTIATED`,`NEG_FLOOR`}),
  calls `plan_offer`, persists the agreed price, and returns `action` (`offer` / `ask_itemisation`
  / `escalate`) + a `customer_safe_summary`. Each further haggle advances one rung.
- **Facility cost** flows only into the backend floor math and is **never surfaced** (CLAUDE.md §7)
  via `_facility_cost_for_order()` (best-effort; returns None offline → the agent holds at the
  standard max and escalates rather than inventing a deeper price).
- **`get_order_summary`** now reflects any persisted negotiated total (`_negotiated_total`) instead
  of reverting to full price.
- **Prompt** discount paragraph rewritten: quote full price first; on haggling call
  `negotiate_order_price`; present exactly what it returns; on `escalate` call `request_human_support`;
  never invent/stack/free-lance a discount or go below the tool's offer.

## Files created
- None. (Negotiation-tool tests were added to the existing `test_booking_tools.py` +
  `test_negotiation.py`; `plan_offer` composition lives in `services/negotiation.py`.)

## Files modified
- `settings.py`, `services/pricing.py`, `services/booking_flow.py`, `services/negotiation.py`,
  `agents/whatsapp_agent/booking_tools.py`
- `tests/test_order_discount.py` (autouse fixture enabling the flag → validates the preserved
  rollback path), `tests/test_booking_tools.py` (old discount-tool test → negotiation-tool tests),
  `tests/test_negotiation.py` (`plan_offer` coverage)

## API / DB / UI / integrations
- **API endpoints:** none. **DB:** **no migration** — negotiation state reuses existing discount
  columns. **UI:** none. **Integrations:** none.
- **Agent behaviour (changed):** the agent now quotes the **full price** and discounts **only via
  negotiation** (ladder → floor → escalate). The tool `calculate_applicable_order_discount` no
  longer exists as a schema (renamed `negotiate_order_price`; alias kept in the executor).

## What is mock-only / live / deferred
- **Mock-only:** all logic tested offline (`LLM_PROVIDER=mock`, fake repo). No live WhatsApp/LLM/Stripe.
- **Deferred (Stage 3b / follow-ups):** min-order delivery-fee tool + express-surcharge tool
  (Stage 1 engines exist, not yet exposed); **live facility-cost lookup** in `_facility_cost_for_order`
  (floor currently reachable only when a cost is provided — otherwise escalates safely); the
  **5-minute ghost auto-advance** (needs a scheduler; the tool advances on each haggle instead).
- **FSM fallback:** the deterministic path also stops auto-discounting (full price); it has no
  negotiation tool, so haggling there simply quotes full price — acceptable, Claude orchestration
  is the default.

## Tests run
```
cd apps/whatsapp-agent
./.venv/Scripts/python.exe -m pytest tests/test_negotiation.py tests/test_booking_tools.py \
  tests/test_order_discount.py -q
./.venv/Scripts/python.exe -m pytest tests/ -k "discount or vat or price or summary or aggregation" -q
./.venv/Scripts/python.exe -m pytest tests/test_final_pricing.py tests/test_catalogue_pricing.py \
  tests/test_pricing_management.py tests/test_booking_flow.py tests/test_item_booking_flow.py \
  tests/test_webhook.py tests/test_webhook_delivery.py tests/test_anthropic_tool_loop.py \
  tests/test_agent_prompt_persona.py -q
./.venv/Scripts/python.exe -m ruff check <all changed files>
```
## Test results (honest)
- Negotiation + booking-tools + order-discount (flag path): **45 + 50 passed**.
- discount/vat/price/summary/aggregation selector: **118 passed**.
- Broad pricing/booking/webhook/prompt regression: **145 passed**.
- ruff on all changed files: **All checks passed**. (4 pre-existing unused-import warnings in
  untouched test files were left out of scope.)
- Full suite not run (README: large; targeted runs).

## Acceptance criteria
1. ✅ Automatic discount retired by default; full website price quoted (spec §2.1). Rollback flag kept.
2. ✅ `negotiate_order_price` drives the §3 ladder (10→20 / 15→25, non-stacking) with the founder
   worked example reachable (60 → 20% → 48; cost 30 → floor 34.50).
3. ✅ Facility cost never surfaced — only the offered/floor price returned to the model.
4. ✅ Itemisation guard (no firm total → cannot negotiate a number) and below-floor → escalate.
5. ✅ Non-breaking to the wider system — all touched regression suites green; legacy auto engine
   preserved + still tested behind the flag.

## Known limitations / next steps
- Floor is only reachable when `_facility_cost_for_order` returns a cost — **live facility-rate
  lookup wiring is the top follow-up**; until then deep haggling escalates to a human (safe).
- Ghost-timer auto-advance deferred (scheduler); `agent_name` + Qatar price list still open.
- **Next: Stage 3b** — expose min-order delivery-fee + express-surcharge tools (Stage 1 engines);
  then Stage 4 (villa/wedding/couture routing), Stage 5 (privacy tests), Stage 6 (regression
  scenarios + replay).
