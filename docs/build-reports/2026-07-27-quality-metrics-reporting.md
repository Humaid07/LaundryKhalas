# Build Report — Quality-Metrics Reporting (Agent Hardening Slice 5)

- **Date:** 2026-07-27
- **Objective:** Add deterministic quality-metrics rollups (conversion, repeat rate, escalation rate, breakdowns by service / country / segment) over orders/flags/turns/customers, **excluding B2B** from consumer conversion, with a read API for the ops dashboard.

## What was built
- **`services/metrics.py`** (pure) — divide-by-zero-safe `ratio`/`pct`, and `build_quality_report(raw)` assembling raw counts into the structured report with computed rates (numeric coercion so SQL `Decimal` sums never mix with floats).
- **`db/repositories/metrics_repo.py`** — deterministic SQL aggregates: `_consumer` (total / with-confirmed / repeat / booking-started / price-enquiry / confirmed-orders / revenue — **excludes `is_b2b` + demo**), `_escalations` (conversations / flagged / open complaints / pending tasks open+overdue), `_by_service`, `_by_market` (B2B-excluded), `_by_segment` (by CRM lifecycle), `_b2b`. `quality_report()` composes them + calls the pure assembler; returns an all-zero report outside supabase mode.
- **`api/internal_metrics.py`** — `GET /api/internal/metrics/quality`, registered in `main.py` under `require_ops`.

## Metrics produced
- **Consumer conversion:** customer-conversion-rate, booking-started→confirmed rate, price-enquiry customers, confirmed orders + revenue + avg order value.
- **Repeat:** repeat customers (2+ confirmed cycles) and repeat rate.
- **Escalation:** flagged-conversation rate, open complaints, open + overdue pending tasks.
- **Breakdowns:** confirmed by service, confirmed by market/country, customers by CRM segment.
- **B2B:** open leads (kept out of the consumer numbers).

## Why
There was no aggregation over the operational data — the historical benchmarks (≈40% chat→booking, ≈10.7% repeat) had nowhere to live. These rollups let future prompt/model changes be evaluated on conversion/trust, not speed.

## Database / agent / API / UI
- **DB:** none (read-only over existing tables). **API:** one ops route. **Agent/UI:** none this slice (dashboard cards consume the endpoint later).

## Mock-only / live
- Read-only against dev/test Supabase; all-zero outside supabase mode. No external calls, no LLM.

## Tests run + results
- **`tests/test_metrics.py` — 5 passed** (divide-by-zero safe rates; report assembles the ~40%/~10% benchmark shape; all-zero on empty; repo SQL excludes B2B + demo and uses the 2+ repeat rule).
- **Full backend suite — 690 passed** (685 → 690, +5), no regressions.
- **Live Supabase smoke:** `quality_report()` returned real figures (customer conversion 50%, repeat rate, 12 conversations / 5 flagged, revenue AED 47.25) — validated the CTE, joins, filters and Decimal coercion end-to-end.

## Known limitations
- `price_enquiry_customers` / booking-started→confirmed depend on the funnel-stage feed (Slice-1 `funnel_stage`, populated on recompute); until price-enquiry tracking lands they read low.
- `by_segment` shows `unknown` for customers not yet recomputed (recompute currently fires on confirm/escalation; a batch recompute is a follow-up).
- No time-window filtering yet (all-time only); date ranges + campaign/facility breakdowns are follow-ups.

## Security / privacy notes
- Aggregate counts only — no PII. B2B excluded from consumer conversion. Endpoint is ops-guarded.

## Commands
- Tests: `cd apps/whatsapp-agent && ./.venv/Scripts/python.exe -m pytest tests/test_metrics.py -q`
- Endpoint: `GET /api/internal/metrics/quality` (ops auth).

## Next recommended step
Slice 6 — sanitized evaluation dataset: a PII-sanitizer + structured eval-record format, plus scenario tests (fragmented booking, price-enquiry conversion, bespoke, structured complaint, duplicate-webhook idempotency).
