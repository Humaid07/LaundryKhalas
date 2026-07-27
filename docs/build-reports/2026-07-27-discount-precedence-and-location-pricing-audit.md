# Build Report — Discount Precedence (15%/20%) + Location-Based Pricing Audit & Scope

**Date:** 2026-07-27
**Status:** Discount-precedence increment **implemented + tested**. The larger location/facility-routing/margin/bespoke subsystem is **audited and scoped** — not built this pass (see §Why and §Remaining).

---

## 1. Objective (from the task)
A production-ready location-based pricing, facility-routing, margin, discount and bespoke-service quotation workflow. This report covers what was delivered now, the architecture found, and an honest plan + coordination decision for the remainder.

## 2. Architecture found (audit)
- **Pricing is already correct & VAT-inclusive** (committed `94d0599`): all customer money routes through `services/money.py`; catalogue prices are treated as final (AED 60 → 60, no ×1.05); `services/pricing.py` / `services/catalogue.py` / `price_resolver` / `public_pricing` all show published prices unchanged with no VAT wording. The runtime source of truth is the published DB catalogue (`config/laundry_catalogue.json` seeded to Supabase + Pricing Management `catalogue_version_items`) — the website is **not** scraped per conversation.
- **Automatic order discount** existed (15% over AED 100, config-driven, Decimal, snapshotted, applied once).
- **Message aggregation** (durable turns, debounce, one-reply-per-turn) exists and is preserved.
- **No margin model, no normalized customer-address model, no Stripe/payment code** anywhere.
- **A concurrent session is actively building a facility subsystem** in the same tree (uncommitted): `apps/facility-dashboard/`, `facilities` table (migration `000016`: code/name/area/city/capacity/operating_status — **no** lat/long, service radius, market, per-service capabilities or rate structure), `facility_*_repo.py`, `api/facility.py`, `services/facility_orders.py`, `services/facility_notifications.py`, RBAC changes (`api/deps.py`, `roles.ts`, `services/auth.py`), migrations `000016`–`000020`. This is a **partner portal**, not the geo-routing/rate/margin engine this task needs.

## 3. Delivered this pass — discount precedence (15% / 20%)
Extends the committed discount engine; lives entirely in already-owned pricing code (no facility dependency, no conflict with the concurrent session):
- `config/order_discounts.json` — added `ORDER_OVER_200_DISCOUNT_REQUESTED` (threshold 200, 20%, `requires_discount_request: true`, priority 20) alongside the 15% rule (priority 10); both versioned.
- `services/discount.py` — rewritten with a deterministic single-winner precedence (`resolve_rule`): highest-priority qualifying rule wins, tiers **never stack**. `evaluate(subtotal, total_is_known, discount_requested)`. Added `detect_discount_request(text)` NLU ("make it cheaper", "best rate", "that's expensive", "any offers"…). Snapshot now records `discount_requested` + `discount_rule_version`.
- `services/pricing.py` — `calculate_estimate(..., discount_requested=False)`; `Quote` carries `discount_requested` + `discount_rule_version`; the summary shows the correct percentage dynamically.
- `services/booking_flow.py` — `Booking.discount_requested` (sticky, from the row); threaded into `_pricing_updates` / `_quote_for`.
- `db/repositories/orders_repo.py` — `discount_requested` in the write-whitelist + surfaced in the pricing block.
- `api/evolution_webhooks.py` — detects a discount request per turn and persists the **sticky** `discount_requested` flag on the open order (records intent only; never invents a discount). `_booking_from_row` + `booking_tools._booking_from_row` map the flag; `get_order_summary` passes it.
- Prompt guidance (`booking_tools.py`) — the agent acknowledges discount requests warmly, never promises a specific discount before the exact total is known, never invents a cheaper rate, and reads the percentage from the tool (backend decides).
- Migration `000021` — `orders.discount_requested` boolean.

**Precedence verified:** 100 → none · 100.01 → 15% · 180 (req or not) → 15% · 200 + req → 15% (200 not > 200) · 200.01 + req → 20% · 250 + req → 20% · 250 no-req → 15%. Never 35%. Recompute is idempotent (no stacking on summary regen / duplicate webhook / reopen).

## 4. Tests
- `tests/test_order_discount.py` extended: precedence table, non-stacking, requested-vs-not, snapshot (`discount_requested` + version), and NLU detection (true/false sets).
- Full suite (fresh run, DB cleaned first): **600 passed, 0 failed** (includes the concurrent session's facility tests + the new discount tests). Note: running a heavy *subset* in isolation surfaces a **pre-existing** Windows SQLite seed-collision flake (`UNIQUE constraint failed: orders.order_id`, documented in `tests/conftest.py`) on ~2 fixture setups — unrelated to this logic (it hits pure-function tests and differs each run; the full clean run is green).

## 5. Why the facility/margin/bespoke subsystem was NOT built this pass (honest)
1. **Concurrent-session conflict.** Another session is actively building the facility subsystem (uncommitted `facilities` table, repos, portal, RBAC, migrations `000016`–`000020`, and `main.py` facility routers). Creating my own facility/rate/capability/quote tables, editing `main.py`/`deps.py`/`roles.ts`, or adding a second `facilities` model would **clobber or duplicate their in-flight work**. Per the repo's git-safety rules I must not overwrite uncommitted work.
2. **Scale.** The remaining spec (customer-address model, facility geo + capabilities + rates, margin rulebook with versioning/publish states, nearest-then-cheapest routing with radius expansion + tie-breaks, bespoke media capture + consent + secure sharing, `facility_quote_requests`/`recipients`/`facility_quotes`/`customer_quotations`, ~17 Anthropic tools, 7 Operations sections, RBAC for facility costs/margins, Stripe consistency, and ~40 test areas) is a multi-subsystem program, not a single-session change. Attempting it all now would produce unreviewable, untested, conflict-prone code.
3. **Honesty rule.** The task itself says: do not claim external facility requests were sent unless the integration succeeds, and never invent facility availability/margins/quotes. Wiring the agent to "ask for location to check a nearby facility" before the facility-rate engine exists would make the agent promise something it can't do — so the conversational discount behavior was kept truthful (acknowledge + apply the automatic tier), and the location→facility flow is deferred to the facility build.

## 6. Remaining work (proposed staged plan, needs a coordination decision)
Build **on top of** the concurrent session's `facilities` table once it lands (not a parallel duplicate):
1. **Extend `facilities`** with lat/long, `service_radius_km`, `market`, `accepts_orders`, `bespoke_capable`. New tables: `facility_service_capabilities`, `facility_rates` (versioned, RBAC-restricted).
2. **`customer_addresses`** normalized model (reuse the existing order pickup lat/long/area/emirate fields) + `resolve_customer_location` tool.
3. **Margin rulebook** (versioned, publish states) + resolver + `calculate_customer_quote` (facility_cost + margin, capped at the published exact price, floor-guarded, human-review on no-rule).
4. **Facility routing** (nearest-then-cheapest, radius expansion to a max, tie-breaks) + internal snapshots.
5. **Bespoke workflow**: `facility_quote_requests`/`recipients`/`facility_quotes`/`customer_quotations`, mandatory photo + location, consent, secure media, minimal-data sharing, Operations queue (no external channel claimed unless it succeeds).
6. **Operations UI + RBAC** for Facility Network / Rates / Margins / Discount Rules / Bespoke queues; permissions for viewing/editing facility costs & margins.
7. **Anthropic tools** (grounded, schema-validated, idempotent) per the spec list.
8. **Stripe** consistency layer (mock until approved) using the final approved quotation.

## 7. Manual testing ready now (discount)
From the two approved numbers: build an exact order over AED 100 → 15% shown, no VAT line. Ask "can you make it cheaper?" then build an exact order over AED 200 → 20% shown (never 35%). An exact AED 200 with a request → still 15%. AED 100 → no discount.

## 8. Business/coordination decision needed
How to proceed on the facility subsystem given the concurrent session: (a) I build the geo-routing/margin/bespoke layers on a branch and rebase onto their facility work once committed, (b) wait for their facility model to land then extend it, or (c) they extend `facilities` and I own margins/routing/bespoke. This determines the safe next step.
