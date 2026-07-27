# Build Report — Facility Rates + Margin + Geo (Agent Hardening Slice 9, mock)

- **Date:** 2026-07-28
- **Objective:** Build the deterministic backend for the location-based better-rate workflow: service-availability per facility, internal rates, margin rules, and geo — so a quote can pick the lowest-cost qualified nearby facility, apply margin, and return ONLY the customer price (cost + margin never exposed). Mock rates.

## What was built
- **`services/facility_pricing.py`** (pure) — `apply_margin` (percentage/fixed, Decimal HALF-UP), `haversine_km` (distance, None on missing coords), `pick_lowest` (lowest rate → distance tie-break → code), `customer_quote` (customer-safe fields only — no cost/margin).
- **`db/repositories/facility_pricing_repo.py`** — `candidates_for_service` (facilities that OFFER the service, active + `accepts_orders` + market match, with rate + distance), `get_margin_rule` (bespoke > service > default precedence), `quote_for_service` (lowest qualified rate + margin → customer price; None when nothing qualifies → caller falls back to the published price).
- **Migration `20260728_000027_facility_rates_margin.sql`** — adds geo/market/`accepts_orders`/`service_radius_km` to `facilities`; new `facility_services`, `facility_rates`, `margin_rules`; **mock seed** (both seeded facilities get coords, service coverage, internal rates, and a default 40% + bespoke 55% margin rule).

## Why
The audit flagged facility routing as area/city/emirate + soft-capacity only — no service-availability, no rates, no margin, no geo. The spec's better-rate workflow needs all of these, with facility cost/margin strictly hidden from the customer (CLAUDE.md §7). This slice delivers that backend.

## Selection logic
Qualified = offers the service (`facility_services.offered`) + active + `accepts_orders` + not closed/paused + market match. Among those: **lowest internal rate wins**, distance (haversine) is the tie-break, then facility code. The active **margin rule** (bespoke > service-specific > default) is applied to the chosen rate → the customer price. Only `{facility_id, facility_code, customer_price_aed, currency, distance_km}` is returned.

## Database / agent / API / UI
- **DB:** migration 000027 (3 tables + facility columns + mock seed). **Agent/API/UI:** none this slice — `quote_for_service` is the backend capability; wiring it into the agent's discount/location flow is the documented next step (a larger behavioural change).

## Mock-only / live
- All rates + margins are MOCK (seed). The selection/margin/geo logic is real and live-validated. Applying the quote in the live booking/discount flow is deferred.

## Tests run + results
- **`tests/test_facility_pricing.py` — 10 passed** (percentage + fixed margin, Decimal rounding, haversine none/roughly-correct, lowest-by-rate + distance tie-break, quote hides cost/margin, repo filters offered/active/accepts + margin-rule precedence).
- **Full backend suite — run after the slice** (final regression).
- **Live Supabase smoke:** applied 000027; `quote_for_service` returned WASH_FOLD → AUH (28 + 40% = **39.20**), CLEAN_PRESS → Marina (6 + 40% = **8.40**), SHOE_CARE bespoke → AUH (30 + 55% = **46.50**), unknown service → None. Confirmed lowest-rate selection + margin precedence + hidden cost end-to-end.

## Known limitations
- Rates/margins are mock; real facility rate cards + business margin rules are a business-data follow-up.
- `quote_for_service` is not yet wired into the live discount/location workflow or the agent — the deterministic backend is ready but not invoked in a booking turn.
- Radius (`service_radius_km`) is stored but not yet enforced as a hard cutoff; distance is a tie-break only.
- No per-item vs per-order rate modelling (single rate per service_code).

## Security / privacy notes
- Facility cost + margin NEVER leave the repo — `customer_quote` returns only the final price (verified by test). Selection is backend-only.

## Commands
- Tests: `cd apps/whatsapp-agent && ./.venv/Scripts/python.exe -m pytest tests/test_facility_pricing.py -q`
- Apply migration (dev/test): execute `supabase/migrations/20260728_000027_facility_rates_margin.sql`.

## Next recommended step
Wire `quote_for_service` into the discount/location flow (Slice-agent path): when a customer asks for a better rate and shares a location, resolve coords → `quote_for_service` → present the customer price + apply the single order-level discount, all cost/margin hidden. Then supply real rate cards to replace the mock seed.
