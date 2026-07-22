# Service Taxonomy — Architecture

**Status:** Live (mock-safe) · **Last synced to website:** 2026-07-22
**Source of truth:** `apps/whatsapp-agent/config/laundry_services.json`
**Live reference:** https://laundrykhalas.com/en-ae/personal-laundry/

---

## 1. Why this exists

Before this change there were **four disjoint service lists** in the codebase
(the WhatsApp agent config, the `laundry_class` KB, the SEO mock sources, and the
admin dashboard), none of which matched the live LaundryKhalas website. A
customer could say "I need dry cleaning for two suits" and the agent might store
a service name the dashboard didn't recognise, or invent a price.

This module makes **one canonical catalog** — synced to the live personal-laundry
pages — that every surface reads from: the WhatsApp agent, order extraction, the
Supabase order rows, the dashboard filters, and the SEO agents.

## 2. The canonical catalog

`apps/whatsapp-agent/config/laundry_services.json` holds the 8 live services.
Each service carries:

| field | meaning |
|---|---|
| `service_id` / `key` | canonical id, e.g. `boutique_clean_press` (`key` is the back-compat mirror) |
| `display_name` / `label` | UI label, e.g. `Boutique Clean & Press` |
| `aliases` / `keywords` | free-text phrases that resolve to this service |
| `category` | cluster key (`dry_cleaning`, `shoe_care`, …) used by SEO |
| `unit_type` | `bag` \| `item` \| `pair` \| `set` \| `sqm` |
| `starting_price_aed` | "from" price verified from the live site |
| `description` | live site copy |
| `eligible_items` | example items the service covers |
| `market_availability` | UAE emirates live today |
| `requires_measurement` | true for `sqm` services |
| `requires_manual_quote` | true → the agent must NOT auto-quote a total |
| `active` | whether the service is offered |
| `source_url` | provenance |

The file also carries `promotional_items` (verified promo prices — Sports
Sneakers, Formal Shoes, Shirt, Trousers/Jeans, Wash&Fold 12kg, Jeans Length
Cutting, Pant Waist Fitting, Carpet/Curtain per sqm) and `service_promises`
(60-minute pickup, stain protection, next-day delivery, WhatsApp booking, free
valet pickup, GPS tracking, eco-friendly, hung/folded delivery).

### The 8 services

| service_id | display name | from | unit | manual quote |
|---|---|---|---|---|
| `premium_wash_fold` | Premium Wash & Fold | AED 60 | bag | no |
| `boutique_clean_press` | Boutique Clean & Press | AED 11 | item | no |
| `steam_pressing_only` | Steam Pressing Only | AED 6 | item | no |
| `luxe_bed_bath_care` | Luxe Bed & Bath Care | AED 29 | set | no |
| `artisan_shoe_restoration` | Artisan Shoe Restoration | AED 35 | pair | no |
| `luxury_bag_spa` | Luxury Bag Spa | AED 60 | item | **yes** |
| `tailoring_alterations` | Tailoring & Alterations | AED 20 | item | **yes** |
| `deep_carpet_curtain_care` | Deep Carpet & Curtain Care | AED 15 | sqm | **yes** |

> **Note:** `Luxury Bag Spa` was found on the live site during the crawl and is
> NOT in the original task spec's 7-service list — it is included because the
> live website is the source of truth.

## 3. How each surface reads the catalog

```
                 config/laundry_services.json  (single source of truth)
                              │
        ┌─────────────────────┼──────────────────────────────┐
        │                     │                              │
   rules.py accessors   seo_agents/taxonomy.py        apps/admin/lib/dashboard/
   (service_catalog,    (service_clusters,            service-catalog.ts
    service_options,     taxonomy_service_ids)        (checked-in TS MIRROR)
    service_by_id, …)          │                              │
        │                      │                              │
   ┌────┴─────┐           SEO mock_sources.SERVICES     mock-data SERVICES +
   │          │           + TOPICAL_GAPS clusters       types ServiceType +
 tools.py  order_          (content plan)               every mock Order.service
 (detect,  extraction.py                                (filters bite on real names)
  price)   (service_key, unit_type,
   │        requires_manual_quote)
   │            │
 agent.py   orders_repo.py  → Supabase orders row:
 (pricing    service_id, service_display_name,
  facts,      unit_type, requires_manual_quote, amount
  buttons)   → OrderRead → /api/orders → dashboard live orders
```

- **WhatsApp agent** — `SERVICE_ACTIONS` (the "which service?" quick-reply
  buttons) come straight from the catalog, so they are always the 8 live
  services. `services/service_selection.py` adds the `Not sure / Help me choose`
  option and the "ask, don't guess" logic.
- **Order extraction** — `services/order_extraction.py` resolves a service from
  the customer's words via the catalog aliases and stamps `service_key`,
  `unit_type`, and `requires_manual_quote` onto the `OrderDetails`.
- **Supabase** — migration `20260722_000004_service_taxonomy.sql` adds
  `service_id`, `service_display_name`, `unit_type`, `requires_manual_quote` to
  `orders`. `orders_repo` writes them on capture and returns them via `OrderRead`.
- **Dashboard** — `service-catalog.ts` mirrors the catalog; `SERVICES` (the
  global Service filter) and the `ServiceType` union derive from it. Live orders
  render `service_display_name`.
- **SEO agents** — `seo_agents/taxonomy.py` derives one content cluster per
  service (plus an umbrella "personal laundry pickup and delivery" cluster) and a
  service × market landing-page matrix (Dubai, Abu Dhabi, Sharjah, Ajman, Ras Al
  Khaimah live; Doha, Riyadh configured as future markets).

## 4. Pricing safety (RULE 7 / 8)

- Starting prices are the live "from" prices — verified, not invented.
- For `requires_manual_quote` services (bag spa, tailoring, carpet/curtain) the
  agent **never** quotes an exact total. On a pricing question it says the team
  will confirm; on capture, `orders_repo._estimate_amount` returns `null`.
- For firm per-item services (boutique clean & press, steam pressing) a **floor**
  estimate is computed as `quantity × from-price` (min-clamped) and stored in
  `amount` — clearly an estimate, not a promise.
- Nothing here changes live pricing or publishes website changes.

## 5. Cross-surface consistency check

`services/taxonomy_sync.py` compares the four surfaces (backend / WhatsApp / SEO
/ dashboard mirror). It is exposed two ways:

- **CLI:** `python scripts/verify_service_taxonomy.py` — prints a report, exits
  non-zero on drift (CI-friendly).
- **API:** `GET /api/service-taxonomy/health` → `{ in_sync, mismatches, surfaces }`.
  The dashboard's `ServiceTaxonomyWarning` component polls this (behind the live
  flag) and shows **"Service taxonomy mismatch detected."** when a surface drifts.

Because the WhatsApp and SEO surfaces are *derived* from the catalog in code,
they can only drift by hand-editing; the dashboard `service-catalog.ts` mirror is
the one file a human must keep in sync — the check guards exactly that.

## 6. Not touched / deferred

- The separate `laundry_class/` LangGraph agent keeps its own markdown KB
  taxonomy (per-item price tables, `inspection`-based manual quote). Aligning it
  is a follow-up; it is a distinct agent with a different pricing model.
- No live pricing changes, no website publishing, no live external calls.

## Related

- [[2026-07-22-service-taxonomy-sync]] (build report)
- [[service-taxonomy-test-script]] (test checklist)
- [[seo-agent-system]]
