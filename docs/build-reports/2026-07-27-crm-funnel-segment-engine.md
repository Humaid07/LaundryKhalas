# Build Report — CRM Funnel + Segment Engine (Agent Hardening Slice 1)

- **Date:** 2026-07-27
- **Objective:** Add a deterministic, backend-authoritative CRM layer (single `lifecycle_stage`, single `funnel_stage`, non-exclusive `segments`) derived from a customer's orders + escalation flags — the foundation the spec's metrics, campaign attribution and HubSpot sync all build on. This is Slice 1 of the multi-slice WhatsApp-agent production-hardening program.

## Context — audit first
A five-way read-only audit confirmed most of the brief is **already built** (message aggregation 5/15s, VAT-inclusive pricing, 15%/20% non-stacking discounts with verified boundaries, booking FSM, Anthropic tool-use loop + bounded rounds + single fallback, aliases, SLA/Express, facility routing, 500 tests). The CRM/marketing/attribution layer was the largest genuine gap. Full audit + staged roadmap recorded in the session.

## What was built
- **`services/crm_segments.py`** — a PURE, side-effect-free engine. `CustomerFacts` (aggregates) → `evaluate()` → `CrmResult{lifecycle_stage, funnel_stage, segments}`. Thresholds from `config/crm_segments.json` (never hardcoded). Deterministic; the LLM never assigns these (CLAUDE.md: deterministic backend stays authoritative). Money coerced via `services.money.to_decimal`.
- **`config/crm_segments.json`** — thresholds: repeat ≥2 confirmed, high-value ≥AED 500 LTV, price-sensitive ≥2 discount requests or ≥3 price enquiries w/o booking, inactive ≥60 days, campaign window 30 days.
- **`db/repositories/crm_repo.py`** — `gather_facts()` (SQL aggregates: confirmed count via `confirmed_at`, lifetime value, discount-request count, bespoke via `requires_manual_quote`, active draft, open complaint + B2B via `agent_flags`⋈`conversations`, last activity), `recompute_for_customer()` (best-effort, never raises; persists the cache in one UPDATE), `get_crm_profile()` (dashboard read).
- **Migration `20260727_000022_crm_segments.sql`** — adds to `customers`: `lifecycle_stage`, `funnel_stage`, `segments jsonb`, `confirmed_order_count`, `lifetime_value`, `discount_request_count`, `price_enquiry_count`, `has_open_complaint`, `is_b2b`, `last_order_at`, `last_activity_at`, `segments_computed_at` + indexes. Additive + idempotent.
- **Wiring** (`api/evolution_webhooks.py`): `crm_repo.recompute_for_customer(customer["id"])` at two deterministic points — first-time **booking confirm** and **escalation/complaint** raise. Best-effort; never blocks the customer reply.

## Segment / lifecycle rules
- **Segments (non-exclusive, canonical order):** repeat_customer, new_customer, high_value, price_sensitive, bespoke, campaign_responder, complaint_open, b2b_lead, inactive.
- **lifecycle_stage (single, precedence):** b2b_lead > complaint_open > repeat_customer > active_customer > inactive > lead.
- **funnel_stage (single, highest reached):** BOOKING_CONFIRMED > BOOKING_STARTED > PRICE_ENQUIRY > NEW_ENQUIRY. (`price_enquiry_count` column exists but stays 0 until the price-enquiry funnel slice.)

## Database / API / UI / agent
- **DB:** migration 000022 (above). No API endpoints or UI added this slice (dashboard read wired in a later metrics slice via `get_crm_profile`). No new Claude tools, no agent-visible behavior change.

## Mock-only / live
- Runs live against the dev/test Supabase. No external services. No LLM calls.

## Tests run + results
- **`tests/test_crm_segments.py` — 18 passed** (boundary tests per threshold from an explicit test config + shipped-config load + Decimal-safe money + deterministic ordering + lifecycle precedence).
- **Full backend suite — 626 passed** (608 → 626, +18), 150s. No regressions from the webhook wiring.
- **Live Supabase smoke:** `recompute_for_customer` on a real customer with an open complaint → `lifecycle=complaint_open, funnel=NEW_ENQUIRY, segments=['complaint_open']`; validated the joins, correlated subqueries, jsonb cast and persistence end-to-end.

## Bugs / issues found (and fixed)
- **Migration drift discovered:** the dev/test Supabase was missing **migration 000021** (`orders.discount_requested`) — a committed feature that was silently broken on this DB (any discount-requested logic would error). Surfaced by the recompute's live smoke (`column "discount_requested" does not exist`). **Applied 000021 and 000022** to the dev/test DB to bring it current.

## Known limitations
- `price_enquiry_count` is not yet populated (needs the price-enquiry funnel slice); until then price-sensitive relies on discount-request count and funnel never resolves to PRICE_ENQUIRY.
- Recompute currently fires on confirm + escalation only; a nightly batch recompute (for inactivity transitions) is a follow-up (a maintenance script hook exists via `recompute_for_customer`).
- No dashboard UI consumes the CRM profile yet.

## Security / privacy notes
- No PII added to any customer-facing surface. Segments/lifecycle are internal ops fields. `agent_flags` join is scoped strictly by `conversations.customer_id`. Recompute never logs phone/address.

## Commands
- Tests: `cd apps/whatsapp-agent && ./.venv/Scripts/python.exe -m pytest tests/test_crm_segments.py -q`
- Apply migration (dev/test): execute `supabase/migrations/20260727_000022_crm_segments.sql` against the dev/test Supabase (additive/idempotent).

## How to verify manually
1. Apply migrations 000021 + 000022 to the dev/test DB.
2. Run a recompute for a customer with confirmed orders → expect `repeat_customer`/`active_customer` + `lifetime_value` populated.
3. Raise a complaint on a conversation → recompute → `has_open_complaint=true`, `lifecycle_stage='complaint_open'`.

## Next recommended step
Slice 2 — structured complaints table + the 7 durable `AWAITING_*` pending operational tasks (turn "I'll check with the facility" promises into real tracked tasks), wired into escalation with new `create_complaint` / `create_pending_task` Claude tools.
