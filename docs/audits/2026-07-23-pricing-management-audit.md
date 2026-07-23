# Audit — Pricing Management & Shared Dynamic Pricing (pre-build)

**Date:** 2026-07-23 · Read-only audit for the "Admin Pricing Management + Shared Dynamic Pricing" task. No code changed.

## Summary verdict
A **real item-level catalogue + VAT pricing engine already exists** (recently built, see [[2026-07-23-service-catalogue-pricing]]) — this task **extends it into a pricing-management + publishing + public-API system**, it does not rebuild it. The public **website is external** (not in this repo), so website wiring is **Phase 2 (deferred)**; a public read-only pricing API + docs is the Phase-1 deliverable. There is **no versioning-with-status, promotions, scheduling, audit-with-actor, rollback, granular permissions, public endpoint, cache-invalidation, import/export, or concurrency control** yet — those are the net-new work.

## What exists today

### Catalogue data & runtime (`apps/whatsapp-agent`)
- **Seed:** `config/laundry_catalogue.json` — 9 categories → sub-category services → **120 priced items** (stable codes, aliases, `current_price` (bold), `regular_price` (crossed-out **old** price, *not* a promo), pricing_type/unit, starting/inspection flags, VAT meta).
- **Runtime accessor:** `services/catalogue.py` — reads the **JSON file via `lru_cache`** on the agent hot path (not the DB); `reload_catalogue()` clears the cache. Alias/iron resolution, category/item lookups, price labels.
- **Pricing engine:** `services/pricing.py` — VAT-aware quote (exact / measured-estimate / pending starting-inspection); 5% VAT on the firm portion; never auto-totals a "From"/inspection item. **No** promotion or effective-date logic.
- **DB reads:** `db/repositories/catalogue_repo.py` — DB-first (JSON fallback) reads for the APIs + a `sync_status` (DB↔JSON parity).
- **API:** `api/catalogue.py` → `/api/catalogue`, `/categories`, `/items`, `/items/{code}`, `/resolve`, `/quote`, `/health` — **all behind `require_ops` (auth-guarded)**. No public endpoint.
- **Agent flow:** `services/booking_flow.py` collects category → item → quantity and prices via the engine; snapshots frozen at confirmation.

### Database (`supabase/migrations/20260723_000007_service_catalogue.sql`)
- Tables: `service_categories`, `services`, `service_items`, `service_aliases`, `service_price_versions`.
- `service_items` columns: `item_code`, `canonical_name`/`display_name`, `description`, `pricing_type` (FIXED_PER_ITEM|STARTING_FROM|PER_PAIR|PER_BAG|PER_KG|PER_SQM|INSPECTION_REQUIRED), `pricing_unit`, **`current_price` + `regular_price`** (both exist), `currency` (AED), `is_starting_price`, `requires_inspection`, `requires_measurement`, `bag_limit_kg`, `note`, `active`, `sort_order`, `source`. **No** market, promo, or effective columns.
- `service_price_versions` = a **lightweight append-only per-item price log** (item_code, current/regular price, type/unit, source, recorded_at). **NOT** a catalogue version with a status lifecycle. No version number, no DRAFT/PUBLISHED/ARCHIVED, no publish/rollback, no actor.
- **Historical order protection: DONE.** `orders` already has `line_items jsonb`, `catalogue_category_code/name`, `subtotal_amount`, `vat_rate`, `vat_amount`, `estimated_total`, `pricing_is_estimated`, `pricing_snapshot_at` — frozen at confirmation.

### Auth / RBAC (just built — see [[rbac-auth]])
- **Two roles only:** `admin`, `operations`. Router-level guards `require_admin`/`require_ops`. **No granular permissions** (`pricing.*`) yet. `/api/users` admin management exists.

### Website / CDN / infra
- **The public pricing page is an external site, not in this repo.** This workspace has only: `apps/whatsapp-agent` (FastAPI), `apps/admin` (internal dashboard, deployed to Cloudflare Workers as `dashboardtest` via OpenNext), `apps/whatsapp-chat` (chat simulator). No website/CMS/WordPress/static-site source here. Docs treat `laundrykhalas.com` as an upstream source-of-truth that was **crawled read-only once**.
- **No public API** (`/api/public/*`) today. Currently-open endpoints: `/api/auth/*`, `/webhooks/*`, `/health`.
- **No realtime/cron/cache-purge/revalidation infra** anywhere (no Redis pub/sub, Celery, APScheduler, cron, Cloudflare purge, ISR/`revalidate`). `scripts/expire_drafts.py` is a manually-run idempotent script (the pattern to reuse for scheduled pricing).
- Admin dashboard uses **no** Next ISR/revalidation; R2 incremental cache is commented out.

## WHAT EXISTS vs WHAT'S MISSING

| Capability (task) | Status |
|---|---|
| Item catalogue (categories/services/items/aliases) | ✅ exists |
| VAT-aware pricing engine, starting/inspection safety | ✅ exists |
| Order line-item **snapshots** (historical protection) | ✅ exists |
| `current_price` **and** `regular_price` columns | ✅ exists (regular = old crossed-out, not promo) |
| Per-item price-change **log** | ✅ minimal (`service_price_versions`) |
| Catalogue **versioning w/ status lifecycle** (DRAFT→PUBLISHED→ARCHIVED) | ❌ missing |
| **Draft vs published** separation / preview / explicit publish | ❌ missing |
| **Promotions** (separate promo price, dates, name, market, precedence) | ❌ missing |
| **Scheduled/effective-date** changes + worker | ❌ missing (no scheduler infra) |
| **Immutable audit history** (old/new/field/actor/reason/version) | ❌ missing |
| **Rollback** | ❌ missing |
| **Granular permissions** (`pricing.view/create/edit/publish/rollback/import/export`) | ❌ missing (2 roles only) |
| **Admin pricing APIs** (`/api/admin/pricing/*`) | ❌ missing |
| **Public read-only API** (`/api/public/pricing`) | ❌ missing |
| Agent reads **published DB** catalogue (not JSON lru_cache) + version cache/invalidation | ❌ missing (reads JSON) |
| **Import / export** | ❌ missing |
| **Concurrency control** (optimistic locking) | ❌ missing |
| **Pricing Management UI** (Operations subsection) | ❌ missing |
| **Website integration** | ❌ external site — Phase 2 deferred |

## Key implications for the plan
1. **Extend, don't rebuild** the catalogue tables + engine. Add a version/status layer on top and make the agent read the *published* version.
2. **Website = Phase 2, deferred** (external repo not available). Phase 1 delivers the public API + docs; the site can consume it later. Per task §27/§29 this must be stated, not claimed as "done".
3. **No scheduler infra** → scheduled promotions/price changes use an idempotent, manually-runnable worker script (like `expire_drafts.py`), documented as needing a cron/beat hook for production.
4. **Permission model decision needed** — granular `pricing.*` vs mapping onto the existing 2 roles.
5. **The catalogue foundation is currently UNCOMMITTED** — a stable committed base is needed before layering a large system on it (collision risk).
