# Build Report — Service Taxonomy Sync to Live Website

**Date:** 2026-07-22
**Author:** Engineering (Claude)
**Related:** [[service-taxonomy]] · [[service-taxonomy-test-script]] · [[seo-agent-system]]

---

## 1. Build title
Sync the whole system to the **real LaundryKhalas personal-laundry service taxonomy** (crawled from the live website).

## 2. Task objective
Replace the assorted old/spec service lists with the **live** service catalog and make it a single reusable config that the WhatsApp agent, order extraction, Supabase, the dashboard, and the SEO agents all read from — with pricing safety and a drift-detection warning.

## 3. What was built
A single canonical service catalog (8 live services, rich fields) + accessors, wired into every surface; an "ask, don't guess" service-selection layer; new Supabase order columns; a dashboard TS mirror + mismatch warning; SEO taxonomy derived from the catalog; and a cross-surface sync check (CLI + API). 21 new tests; full suite green.

## 4. Why it was built
The four pre-existing service lists disagreed with each other and with the live site; orders could store unrecognised service names and prices could be invented. The live website is the source of truth.

## 5. Services found from the website
Crawled `https://laundrykhalas.com/en-ae/personal-laundry/`:

| service | from | unit |
|---|---|---|
| Premium Wash & Fold | AED 60 | bag |
| Boutique Clean & Press | AED 11 | item |
| Steam Pressing Only | AED 6 | item |
| Luxe Bed & Bath Care | AED 29 | set |
| Artisan Shoe Restoration | AED 35 | pair |
| **Luxury Bag Spa** (not in task spec — found live) | AED 60 | item |
| Tailoring & Alterations | AED 20 | item |
| Deep Carpet & Curtain Care | AED 15 | sqm |

Promotional items also captured: Sports Sneakers (AED 50), Formal Shoes (55), Carpet/sqm (20), Curtain/sqm (20), Shirt (9), Trousers/Jeans (11), Wash & Fold 12kg (90), Jeans Length Cutting (35), Pant Waist Fitting (35). Promises captured: 60-min pickup, stain protection, next-day delivery, WhatsApp booking, free valet pickup, GPS tracking, eco-friendly, hung/folded delivery.

## 6. Files created
- `apps/whatsapp-agent/services/service_selection.py` — "which service?" clarification + options.
- `apps/whatsapp-agent/services/taxonomy_sync.py` — cross-surface consistency check.
- `apps/whatsapp-agent/seo_agents/taxonomy.py` — SEO clusters + market matrix, derived from the catalog.
- `apps/whatsapp-agent/api/service_taxonomy.py` — `/api/service-taxonomy[/options|/health]`.
- `apps/whatsapp-agent/scripts/verify_service_taxonomy.py` — CLI sync check.
- `apps/whatsapp-agent/tests/test_service_taxonomy.py` — 21 tests.
- `apps/admin/lib/dashboard/service-catalog.ts` — canonical TS mirror.
- `apps/admin/components/dashboard/operations/live/ServiceTaxonomyWarning.tsx` — mismatch banner.
- `supabase/migrations/20260722_000004_service_taxonomy.sql` — additive order columns.
- `docs/architecture/service-taxonomy.md`, `docs/checklists/service-taxonomy-test-script.md`, this report.

## 7. Files modified
- `config/laundry_services.json` — replaced 7 old services with the 8 live services + rich fields (`service_id`, `unit_type`, `starting_price_aed`, `category`, `eligible_items`, `market_availability`, `requires_measurement`, `requires_manual_quote`, `active`, `source_url`) + promo items + promises. Back-compat `key`/`label`/`keywords`/`pricing` retained.
- `rules.py` — added `active_service_catalog`, `service_by_id`, `service_ids`, `service_options`, `promotional_items`, `service_promises`.
- `services/order_extraction.py` — `OrderDetails` gains `unit_type`, `requires_manual_quote`, `service_id`; populated from the catalog.
- `db/repositories/orders_repo.py` — writes/reads the new columns; `_estimate_amount` now returns `null` for manual-quote services.
- `schemas.py` — `OrderRead` gains `service_id`, `service_display_name`, `unit_type`, `requires_manual_quote`.
- `agents/whatsapp_agent/agent.py` + `llm/providers/mock.py` — pricing questions on manual-quote services defer to the team (no invented figure).
- `seo_agents/mock_sources.py` — `SERVICES` + `TOPICAL_GAPS` now derive from / match the canonical services.
- `main.py` — registers the service-taxonomy router.
- Admin dashboard: `lib/dashboard/{types,mock-data,operations-data,whatsapp-inbox,marketing-data,sections,filters.test}.ts`, `lib/dashboard/whatsapp-agent-api.ts`, `lib/types.ts`, `components/dashboard/operations/live/LiveWhatsAppOrders.tsx`, `app/(dashboard)/operations/customer-orders/page.tsx`.
- Tests updated to new taxonomy: `test_quick_actions.py`, `test_order_extraction.py`, `test_orders.py`, `test_chat.py`.

## 8. API endpoints added/changed
- `GET /api/service-taxonomy` — full catalog + promo items + promises.
- `GET /api/service-taxonomy/options` — the agent's service-selection options (+ "Help me choose").
- `GET /api/service-taxonomy/health` — `{ in_sync, mismatches, surfaces }` (drives the dashboard warning).
- `GET /api/orders` (+ order detail) responses now include `service_id`, `service_display_name`, `unit_type`, `requires_manual_quote`.

## 9. Database tables/models changed
`orders` (dev/test Supabase only) — additive nullable columns `service_id`, `service_display_name`, `unit_type`, and `requires_manual_quote` (boolean default false). Migration `20260722_000004_service_taxonomy.sql`. **Not yet applied to a live DB in this session** (see limitations).

## 10. UI pages/components changed
Global **Service** filter now the 8 real services; live orders show `service_display_name`; new `ServiceTaxonomyWarning` banner on `/operations/customer-orders`; all seeded mock rows remapped to the new names so filtering still works.

## 11. Agent behaviour changed
- Booking with no service now **asks which service** (with the 8 options + "Help me choose") instead of silently guessing Wash & Fold.
- Item/word → service mapping updated to the live taxonomy.
- Manual-quote services are never auto-priced in chat.

## 12. Integrations changed
None live. All mock. No live WhatsApp/Stripe/LLM/website calls; the website was read once (read-only crawl) to source the taxonomy.

## 13. What is mock-only
Everything customer-facing: mock WhatsApp, mock orders, dashboard mock rows, SEO mock sources. Estimated prices are floor estimates, not commitments.

## 14. What is live
The service names, units, starting/promo prices, and promises are the **real** values from the live website (verified, read-only). The dev/test Supabase schema change is real (but pending apply).

## 15. What is intentionally deferred
- Aligning the separate `laundry_class/` LangGraph agent's own KB taxonomy.
- Applying migration `…000004` to the live dev/test Supabase DB.
- Auto-generating `service-catalog.ts` from the JSON (kept as a checked-in mirror guarded by the sync check).

## 16. Tests run
- Backend: `pytest -q` (full suite).
- Sync CLI: `python scripts/verify_service_taxonomy.py`.
- Admin: `npx tsc --noEmit`, `npx tsx lib/dashboard/filters.test.ts`.

## 17. Test results
- **Backend: 245 passed, 0 failed.**
- **Sync CLI: exit 0 — "all surfaces are in sync"** (backend / whatsapp / seo / dashboard all 8 ids).
- **Admin tsc: 0 errors** (the ~87 previously-noted Filterable errors did not appear; clean). **filters.test: 45/45.**

## 18. Bugs/issues found
`test_chat.py::test_slots_accumulate_across_turns_not_just_last_message` encoded the OLD behaviour where "laundry pickup" auto-selected Wash & Fold — the exact guess the new spec forbids. Rewritten to assert the correct "ask which service, then accumulate slots" flow. No product bug; the test premise was outdated.

## 19. Known limitations
- Migration not applied to a live DB this session; live "order appears on dashboard with service" is verified at the repo-mapping level, not against live Supabase.
- `service-catalog.ts` is a hand-kept mirror (the sync check guards drift, but a human updates it when the catalog changes).
- `laundry_class/` still has an independent taxonomy.

## 20. Security/privacy notes
No secrets touched. No PII added. Address handling unchanged (still backend-only / masked in lists). The website crawl was read-only and sourced only public catalog data.

## 21. Cost/LLM usage notes
No live LLM calls. One read-only website fetch to source the taxonomy. Sub-agents used for code mapping and the mechanical dashboard rewrite.

## 22. Screens/pages to demo
- WhatsApp test console: "I need a laundry pickup service" → service clarification with 8 options.
- `/operations/customer-orders`: live orders showing the selected service; the mismatch banner (when drift is introduced).
- Global Service filter listing the 8 real services.

## 23. Commands to run
```bash
# backend
cd apps/whatsapp-agent
python scripts/verify_service_taxonomy.py
.venv/Scripts/python -m pytest -q
# dashboard
cd ../admin
npx tsc --noEmit -p tsconfig.json
```

## 24. How to verify manually
Follow `docs/checklists/service-taxonomy-test-script.md` sections B–G.

## 25. Next recommended step
Apply `20260722_000004_service_taxonomy.sql` to the dev/test Supabase project and run one live WhatsApp capture end-to-end to confirm `service_id` lands on the row and renders on the dashboard; then align the `laundry_class/` agent to the canonical catalog.
