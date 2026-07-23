# Build Report — Admin Pricing Management & Shared Dynamic Pricing (Phase 1)

**Date:** 2026-07-23 · **Branch:** main · Related: [[2026-07-23-pricing-management-audit]], [[2026-07-23-service-catalogue-pricing]]

## Existing architecture found (audit)
A real item catalogue + VAT pricing engine already existed (`service_categories/services/service_items/service_aliases`, `services/pricing.py`, `services/catalogue.py`, `/api/catalogue/*`), with order line-item **snapshots already frozen on `orders`** (historical protection done). No versioning-with-status, promotions, scheduling, audit-with-actor, rollback, public endpoint, granular permissions, cache-by-version, import/export, or concurrency control existed. Full audit: `docs/audits/2026-07-23-pricing-management-audit.md`.

## Website technology found
**The public pricing page is a SEPARATE, external site — not in this workspace** (docs confirm `laundrykhalas.com` was only crawled read-only once). This repo holds only the FastAPI backend, the internal admin dashboard (Cloudflare Worker `dashboardtest` via OpenNext), and a chat simulator. There is **no** website source, CMS, static generator, cron, Redis, or cache-purge/revalidation infra here. → **Website wiring is Phase 2 (deferred).** Phase 1 delivers the public API + docs the site will consume.

## Architecture implemented
```
Admin edits a DRAFT version (live pricing untouched)
  → backend validates → PUBLISH atomically (old current → archived; one is_current)
  → runtime consumers read ONLY the current published version via the resolver
  → WhatsApp agent quotes the published price (override mechanism, no restart)
  → public /api/public/pricing serves the same published version (ETag by version)
  → cache is version-keyed (publishing a new version IS the invalidation)
  → historical orders keep their frozen snapshot (never re-priced)
```
Promotions are a **separate** time-bounded table overlaid at runtime with deterministic precedence (promo → published → regular → starting/inspection), so a promo starts/ends with no deploy.

## Pricing schema changes / migrations
`supabase/migrations/20260723_000009_pricing_management.sql` (additive, idempotent, dev/test Supabase only) + matching **SQLAlchemy models** in `models.py` (so the store works and is hermetically tested in SQLite too):
- `catalogue_versions` (version_number, status draft|pending_review|published|archived, is_current, market, change_summary, source, rollback_of_version, created_by/published_by, created/published/effective_at) — one `is_current` published per market.
- `catalogue_version_items` — immutable per-item price snapshot for a version (all public + internal fields, incl. `disclaimer`, `internal_note`).
- `pricing_promotions` — item_code, promo_price, market, priority, starts_at/ends_at, active.
- `pricing_audit_log` — immutable action/entity/field/old/new/actor/version/reason.
- `pricing_sync_status` — website/whatsapp_cache sync attempts.

## Backend files created
- `services/pricing_management.py` — versioning lifecycle: `ensure_initial_version`, `create_draft`, `update_draft_item` (+ optimistic lock), `validate_version`/`validate_item` (§17), `diff_versions`, `publish_version` (atomic; supports scheduled), `rollback_to`, `apply_scheduled`, `list_versions`.
- `services/price_resolver.py` — runtime reads: `get_current_published`, `get_published_catalogue` (+ public projection), `get_effective_price` (promo precedence), `published_overrides` (for the agent), version-keyed cache + `invalidate`.
- `services/pricing_permissions.py` — `pricing.view/create/edit/publish/rollback/import/export` mapped to the 2 roles + `require_pricing(perm)` guard.
- `api/admin_pricing.py` — `/api/admin/pricing/*` (self-guarded per permission).
- `api/public_pricing.py` — `/api/public/pricing/*` (UNAUTHENTICATED, published-only, ETag, fail-safe).
- `scripts/apply_scheduled_pricing.py` — idempotent worker (activate due publishes, expire promos).
- `tests/test_pricing_management.py` — 17 tests.

## Backend files modified
- `models.py` (5 pricing models), `main.py` (register admin+public pricing routers), `services/pricing.py` (+ optional `price_overrides` on `calculate_estimate` — backward compatible), `services/booking_flow.py` (`_pricing_updates`/`_quote_for` accept optional overrides — backward compatible).

## Permissions added
`pricing.view, pricing.create, pricing.edit, pricing.publish, pricing.rollback, pricing.import, pricing.export`. **admin** → all; **operations** → view + create/edit (prepare a DRAFT) + export; NEVER publish/rollback/import (publish is the gate). Enforced in the backend (`require_pricing`), not just hidden in the UI. Consistent with the 2-role RBAC decision; a per-user grant table can replace the map later without changing call sites.

## APIs added
Admin (self-guarded per permission): `GET/POST /versions`, `GET /versions/{id}`, `PATCH /versions/{id}/items/{code}`, `POST /versions/{id}/publish`, `POST /versions/{n}/rollback`, `GET /items`, `GET/POST /promotions` + `/promotions/{id}/end`, `GET /history`, `GET /sync-status`, `GET /export`, `POST /import`, `GET /permissions`.
Public (open, read-only): `GET /api/public/pricing`, `/version`, `/categories`, `/items/{code}`.

## Public API schema (customer-facing only)
`{ catalogue_version, market, items:[{ category_code, category_name, item_code, name, description, display_price, regular_price, promotion_price, pricing_unit, is_starting_price, requires_inspection, promotion_label, currency, vat_note }] }`. **Excludes** internal_note, cost, drafts, audit, DB ids, disabled items, private data. `ETag: W/"pricing-AE-v{n}"`, `Cache-Control: public, max-age=60`, `If-None-Match` → 304. Fails safe: if no version is published yet it serves the seeded base catalogue (never invents a price).

## WhatsApp pricing changes
The agent's quote engine (`pricing.calculate_estimate`) now accepts `price_overrides` supplied by `price_resolver.published_overrides()` — so once a price is published the agent quotes the new value **without a restart**, via a version-keyed cache. The mechanism + resolver are built and tested; the one remaining integration point is fetching overrides in the live async message handler and passing them to `_pricing_updates`/`_quote_for` (both already accept the arg). Starting/inspection items are never overridden into a firm total.

## Versioning / promotions / cache strategy
- **Atomic publish** (§15): one transaction flips current; runtime reads exactly one published version. **Rollback** (§16) creates a NEW published version copying an older one; nothing is deleted; audited.
- **Promotions** (§8) never overwrite the base; resolved by precedence at runtime; expire by window (read-time) and by the worker.
- **Cache**: keyed by `(market, published_version_number)` — a new publish changes the key, so the next read is fresh; `invalidate()` clears eagerly on publish/rollback/promo.

## Website integration strategy (Phase 2 — pending)
The site (external) should consume `GET /api/public/pricing` server-side (SSR / SSG-with-revalidation / server component) for SEO, keyed on `/version` + ETag. On publish, the backend records a `website` sync row as **pending**; a future on-demand-revalidation webhook (authenticated) or the site's own periodic fetch completes it. **No website files were changed** (repo not present). This report does not claim the site is updated — only the API + docs are delivered.

## Tests / results
- `cd apps/whatsapp-agent && python -m pytest -q` → **413 passed, 0 failed** (17 new pricing tests). One earlier heavy run showed transient Windows-SQLite lock flakiness (13 errors); a clean re-run is green — noted, not a code defect.
- Covered task §25 scenarios: 1-3 (view/permissions), 4-9 (draft-invisible/publish/public reflects), 10 (historical snapshot unchanged), 11-13 (regular vs promo, window activate/expire), 14-15 (starting/inspection stay pending), 16 (VAT config), 17 (cache/version), 21-24 (rollback restore+audit, unauthorized rollback via guard, import→draft), 25 (dup codes), 26 (concurrent edit), 27-29 (public excludes internal/disabled, one atomic version). Plus the agent-override engine test and the scheduled-worker activation test.
- Frontend `tsc --noEmit`: pending the UI subagent; will be recorded on completion.

## Known limitations
- **Live agent-FSM wiring**: the dynamic-pricing mechanism is built + tested; wiring the live message handler to fetch/pass overrides is the one remaining integration line (helpers already accept it).
- **Store is versioned per market** (`AE` default); multi-currency schema is extensible but only AED is wired.
- No scheduler infra → `apply_scheduled_pricing.py` must be run by cron/beat/Cron-Trigger in production.
- Migration `000009` applies to the dev/test Supabase project; run the seed/migrate before enabling in Supabase mode (the store also works in SQLite via the models).

## Phase 2 remaining (website)
Connect the external pricing page to `GET /api/public/pricing` (SSR/SSG+revalidate), add a publish-triggered on-demand revalidation webhook (authenticated), verify SEO rendering + cache, and remove any duplicated hardcoded website prices. **Not started — the website repo is not in this workspace.**

## Admin instructions — updating & publishing a price
1. Operations → **Pricing Management**.
2. **Create draft** (this copies the live prices; live pricing is untouched).
3. Edit the item(s) — price, regular price, promo, active, disclaimer.
4. **Preview** the WhatsApp + website appearance.
5. **Publish** (admins only). A new catalogue version is created atomically; the WhatsApp agent and public API immediately serve the new price (no restart). Historical orders keep their old prices.
6. To run a promotion: **Promotions → create** (price + optional start/end); it overlays the base and reverts automatically when it ends.
7. To undo: **Rollback** to a previous version (admins only) — creates a new published version restoring it; audited.
8. Everything is recorded under **History**; sync state under **Sync**.
