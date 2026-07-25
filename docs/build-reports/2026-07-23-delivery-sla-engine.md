# Build Report — Delivery SLA / Turnaround + Express Engine (Phase 4)

**Date:** 2026-07-23
**Status:** Engine + DB + seed + tests complete and green (24 tests). Booking-flow
wiring intentionally deferred (see §Concurrency).

## Objective
Implement database-driven delivery SLA / turnaround, Express eligibility, and the
order delivery estimate (master prompt Phase 4 / §§23–25), so the WhatsApp agent
and orders can show an accurate, non-fabricated delivery promise.

## What was built (all self-contained new files)
- `config/delivery_sla.json` — reviewed SLA rules: per-category defaults + item
  overrides (carpet, sofa cover, duvet/blanket, mascot, wedding/evening dress),
  a safe default rule, Express config (12h, eligible categories, **null**
  surcharge — never invented), `day_type=CALENDAR`.
- `services/delivery.py` — pure engine: `sla_for_item` (item override > category
  default > default), `order_turnaround` (slowest rule wins for combined orders;
  Express only when EVERY item is eligible), `estimate_delivery` (adds the
  turnaround window to the pickup end time), `delivery_options`.
- `supabase/migrations/20260723_000010_delivery_sla.sql` — `delivery_sla_rules`
  table + frozen delivery-estimate snapshot columns on `orders`. **Applied live.**
- `db/repositories/delivery_repo.py` — DB-first rule reads (JSON fallback),
  `sync_status`, `store_delivery_estimate` (freezes the estimate on confirm).
- `scripts/seed_delivery_sla.py` — idempotent migrate+seed. **Seeded live** (15
  rules; `sync_status` → `source=supabase, in_sync=True`).
- `tests/test_delivery_sla.py` — 24 tests, all passing.

## SLA rules encoded (from §23)
Wash & Fold / Clean & Press / Press Only → 24h; Shoe / Bag → 2–3 days; Carpet →
3–4 days; Alterations / Mascot → 2 days; Toy / Sofa cover / Bedding & covers /
Dress → 24h; Duvets & blankets / Wedding-evening dress → 1–2 days; Restoration →
2–3 days. Express = 12h for Wash & Fold / Clean & Press / Press Only only.

## Tests
`python -m pytest tests/test_delivery_sla.py -q` → **24 passed.** ruff clean.
Covers every §23 SLA class, Express eligibility, Express rejected for mixed
orders, slowest-SLA-for-combined, estimate recalculation on pickup/service edit,
safe default for unknown items, and null Express surcharge.

## Concurrency note (why wiring is deferred)
A parallel session is actively building the Pricing Management stack (Phase 7/8:
`price_resolver`, `pricing_management`, `admin_pricing`, `public_pricing`,
migration 000009) and is mid-edit on `booking_flow.py`, `main.py`, `models.py`,
`pricing.py`/`orders_repo`. The full suite currently reports collection errors
from that in-flight work. To avoid corrupting it, the delivery estimate is **not
yet wired** into the booking confirmation summary / order snapshot. The engine +
`delivery_repo.store_delivery_estimate` are ready; wiring is a small, well-scoped
follow-up once the pricing work lands:
1. `booking_flow._summary_text`: add `delivery.order_turnaround(item_codes)` text.
2. Webhook confirm path: call `delivery.estimate_delivery(item_codes,
   pickup_end_time)` + `delivery_repo.store_delivery_estimate`.
3. `orders_repo.to_read`: expose the delivery snapshot for the dashboard.
4. (Optional) a `DELIVERY_MODE_SELECTION` FSM state to offer Express.

## Known limitations / business decisions
- **Calendar vs working days:** currently CALENDAR days (config `meta.day_type`).
  A business decision — flagged, not silently assumed. Working-day calendar math
  is a follow-up.
- **Express surcharge:** null (not configured). Express is offered as a 12h option
  without a fabricated price until the business sets `express_surcharge_aed`.
- **Leather cleaning (1–2 days):** not a distinct catalogue item; leather goods
  fall under Bag Care (2–3 days). Flagged for business confirmation.

## Next step
Wire the engine into the booking confirmation + order snapshot (above) after the
concurrent Pricing Management work settles, then a live delivery-estimate check.
