# Build Report — Item-level Service Catalogue, Pricing Engine & Agent Item Collection

**Date:** 2026-07-23
**Author:** Engineering (Claude)
**Status:** Backend + agent + tests complete and green; live Supabase seed applied; dashboard wired (activates on live order data).

---

## 1. Task objective

Replace the placeholder service-level catalogue (8 branded services, one "from"
price each) with the **real Laundry Khalas item catalogue** from the approved
price-list image, following the required architecture:

```
Approved price list → reviewed structured seed data → PostgreSQL/Supabase catalogue
→ backend pricing & catalogue APIs → WhatsApp agent → Orders dashboard → deterministic tests
```

The database is the runtime source of truth. The WhatsApp agent must never read
the image at runtime; it must collect items + quantities and produce VAT-aware
quotes without ever presenting a starting ("From") or inspection price as a
guaranteed total.

## 2. What was built

1. **Reviewed structured catalogue data** transcribed and verified from the image:
   9 categories → sub-category services → **120 priced items**, with stable codes,
   aliases, pricing types/units, `current_price` (bold), `regular_price`
   (crossed-out), starting-price and inspection flags.
2. **Normalized DB catalogue** (`service_categories`, `services`, `service_items`,
   `service_aliases`, `service_price_versions`) + an idempotent migrate+seed script.
3. **VAT-aware pricing engine** — exact vs estimate (measured) vs pending
   (starting/inspection) lines; 5% VAT applied only to the firm portion.
4. **Catalogue + pricing APIs** (`/api/catalogue/*`).
5. **Agent item-collection sub-flow** inserted into the booking FSM: category →
   (sub-category) → item → quantity/measure → add-another/done → the existing
   proven name→date→slot→address→instructions→confirm path, with a priced quote
   in the confirmation summary.
6. **Order pricing snapshot** columns + JSONB `line_items` frozen at collection
   time, exposed on the order API for the dashboard.
7. **Dashboard order line-items + VAT summary** (defensive; falls back to the
   existing single-amount display for legacy orders).
8. **Deterministic tests** — 41 new (all 24 required scenarios + item-flow).

## 3. Why

The previous catalogue used invented marketing names and a single starting price
per service — it could not price a real multi-item order, had no VAT, no item
catalogue, and no line items. The business needs the real price list to quote
customers correctly on WhatsApp and show accurate order totals to operations.

## 4. Files created

- `apps/whatsapp-agent/config/laundry_catalogue.json` — reviewed seed data (9 categories, 120 items).
- `apps/whatsapp-agent/services/catalogue.py` — cached catalogue accessor + alias/iron resolution.
- `apps/whatsapp-agent/services/pricing.py` — VAT-aware quote engine + quote wording.
- `apps/whatsapp-agent/db/repositories/catalogue_repo.py` — DB-first (JSON fallback) catalogue reads + `sync_status`.
- `apps/whatsapp-agent/api/catalogue.py` — catalogue/pricing API router.
- `apps/whatsapp-agent/scripts/seed_service_catalogue.py` — idempotent migrate+seed.
- `supabase/migrations/20260723_000007_service_catalogue.sql` — catalogue tables + order pricing/snapshot columns.
- `apps/whatsapp-agent/tests/test_catalogue_pricing.py` — 29 pricing/catalogue tests.
- `apps/whatsapp-agent/tests/test_item_booking_flow.py` — 12 item-flow / snapshot / multi-number tests.

## 5. Files modified

- `apps/whatsapp-agent/services/booking_flow.py` — category selection now uses the 9 real categories; new states `waiting_for_subcategory/item/item_quantity/item_measure/more_items`; item resolution, quantity/measure parsing, quote in summary.
- `apps/whatsapp-agent/db/repositories/orders_repo.py` — `_BOOKING_COLS` gains catalogue/pricing columns (+ jsonb cast for `line_items`); `to_read` exposes `line_items`, `pricing`, `catalogue_category`.
- `apps/whatsapp-agent/api/evolution_webhooks.py` — carries the new booking columns; recognizes `sub:`/`item:`/`add_item`/`items_done` selections; final confirmation shows the total.
- `apps/whatsapp-agent/main.py` — registers the catalogue router.
- Dashboard (`apps/admin`): `lib/dashboard/whatsapp-agent-api.ts` (+`LineItemDTO`/`OrderPricingDTO`), `components/dashboard/operations/order-detail/{OrderItemsTable,OrderSummaryStrip,cards,data}.tsx`.
- Tests updated to the new flow: `test_booking_flow.py`, `test_customer_name.py`, `test_multi_order.py`, `test_service_selection_interactive.py`.

## 6. API endpoints added

- `GET /api/catalogue` — meta + categories.
- `GET /api/catalogue/categories` — `list_service_categories()`.
- `GET /api/catalogue/items?category=CODE` — `list_service_items()`.
- `GET /api/catalogue/items/{item_code}` — `get_service_price()`.
- `POST /api/catalogue/resolve` — `resolve_service_alias()` (+ iron ambiguity).
- `POST /api/catalogue/quote` — `calculate_order_estimate()` (VAT-aware).
- `GET /api/catalogue/health` — DB↔JSON parity.

(All under the Operations RBAC guard.)

## 7. Database changes

New tables: `service_categories`, `services`, `service_items`, `service_aliases`,
`service_price_versions`.
`orders` gains: `line_items jsonb`, `catalogue_category_code/name`,
`subtotal_amount`, `vat_rate`, `vat_amount`, `estimated_total`,
`pricing_is_estimated`, `pricing_snapshot_at`, `browse_service_code`,
`pending_item_code`.
Migration `20260723_000007_service_catalogue.sql` — additive + idempotent.

## 8. What is mock / live / deferred

- **Live/real:** the catalogue data (from the approved image), the pricing math,
  the agent item-collection flow, the DB tables, the migration (applied to the
  dev/test Supabase project), the tests.
- **Mock-only:** none of the pricing is fabricated — starting/inspection items are
  never auto-totalled.
- **Deferred / known limitations:**
  - The **informational** "what services do you offer / price question" path
    (general Q&A via `laundry_services.json` + the SEO taxonomy + the dashboard
    service-catalog mirror) still uses the older 8-service marketing taxonomy. It
    is untouched (all its tests stay green). The **booking flow, pricing, order
    snapshots and dashboard order detail** use the new item catalogue. Aligning
    the informational taxonomy to the 9 categories is a follow-up.
  - The dashboard order-detail **page** is mock-fed today; the live line-item
    pricing renders in the Orders **drawer** and activates fully when live
    `OrderWithPricing` data is passed to the detail page.
  - Native WhatsApp interactive lists cap at ~10 rows; a few sub-categories
    (Everyday Wear 11, Traditional Items 17) exceed that. The default shipping
    path is numbered text (handles any length); native-list paging is a follow-up.

## 9. Tests

- **Command:** `cd apps/whatsapp-agent && python -m pytest -q`
- **Result:** **372 passed, 0 failed** (was 362; +41 new, 17 existing updated to the new flow).
- **Required scenarios (task §14):** all 24 covered — items 1-22 in
  `test_catalogue_pricing.py`, 23 (snapshot immutability) & 24 (two numbers /
  shared catalogue / separate state) in `test_item_booking_flow.py`.
- **Lint:** `ruff check` clean on all changed files.
- **Dashboard:** `tsc --noEmit` clean (zero errors).
- **Catalogue sanity:** 9 categories, 120 items; 3×Shirt + 2×Trousers → subtotal
  49, VAT 2.45, total 51.45.

## 10. Security / privacy

No PII involved; catalogue is public business data. Seed script is guarded
(refuses production; requires the dev/test Supabase project). No secrets added.
The LLM never holds the full catalogue — the backend validates the item and
returns the price.

## 11. How to verify manually

```
cd apps/whatsapp-agent
python -m pytest tests/test_catalogue_pricing.py tests/test_item_booking_flow.py -q
python scripts/seed_service_catalogue.py            # apply DDL + seed (dev/test Supabase)
# then: GET /api/catalogue/categories, /api/catalogue/items?category=CLEAN_PRESS,
#       POST /api/catalogue/quote {items:[{item_code:"CLEAN_PRESS_SHIRT",quantity:3}]}
```

## 12. Values that needed interpretation (flagged, none guessed)

- Crossed-out prices stored as `regular_price` (not the selling price): Shirt/Polo
  9 (was 12), Trousers 11 (was 14), Curtain 20/sqm (was 25), Carpet 20/sqm
  (was 36), shoe "From 55/50" (was 110/95).
- Soft Toys given exact prices (not starting) as printed.
- "Alterations" printed under a "shoe & leather" header on the image but is
  tailoring — modelled as its own category with a From-30 starting price.
- Wash & Fold additional weight (AED 7/kg) modelled as a `PER_KG` item charged
  after the bag limit — not auto-added without a stated weight.

Nothing unreadable was guessed.

## 13. Next recommended step

Align the informational service taxonomy (Q&A / SEO / dashboard service-catalog
mirror) to the 9 real categories, and pass live `OrderWithPricing` into the
order-detail page so line-item pricing renders there too. Then a live two-number
WhatsApp manual test of the full item→quote→confirm flow.
