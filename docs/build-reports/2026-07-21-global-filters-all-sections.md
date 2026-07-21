# Build Report — Global Filters Across All Dashboard Sections

**Date:** 2026-07-21
**Area:** `apps/admin` internal Command Center — global filter system

## 1. Task objective

Make the dashboard's global filters (Date, Region, Market, City, Channel,
Service) **truly global**: apply consistently to every section, subsection page
and tab wherever the data has matching fields — not just Overview/Operations/
Sales/Finance. Eliminate filters that *look* active but don't affect data, add
structured filter fields to mock data that lacked them, honour the
Region → Market → City dependency, persist filters across navigation, and show
clean empty states.

## 2. What was built

The filter **engine, provider, cascade, chips and pure-function tests already
existed** and were sound. This task closed the **coverage-and-honesty gaps** an
audit surfaced: many tables/KPIs/charts and whole subsections rendered raw
(unfiltered) data behind a visible filter bar, and several mock arrays lacked
structured geo/date fields.

Delivered:

1. **Engine hardening** (`lib/dashboard/filters.ts`)
   - Broadened date recognition: `rowDate` now reads a priority list of date
     field names (`DATE_KEYS`: createdAt, date, datetime, requestedAt, raisedAt,
     reportedAt, queuedAt, lastContact, lastUpdate, lastGenerated, scheduledFor,
     timestamp, expiry, dueDate, due). Previously only `createdAt/date/datetime`
     were recognised, so the Date filter silently no-op'd on most rows.
2. **Shared honesty UI** (`components/dashboard/ui/states.tsx`)
   - `FilteredEmptyState` — names the active filter context + a **Clear filters**
     button.
   - `SnapshotBadge` — an **"Overall snapshot"** pill shown only while filters
     are active, for aggregate KPIs/charts that are period snapshots (with
     section variants "Global / site-wide", "Brand-wide", "Global / technical").
3. **Structured fields added to mock data** so previously-inert lists filter:
   - Operations: `facilityIssues`, `driverPerformance`, `driverIssues`,
     `orderIssues` now carry `city`; `invoices` now carry `city` + `channel`.
   - SEO: `seoTasks` now carry `city` / `scope:"global"`.
4. **Every inert list wired through the engine + empty states**, and every
   aggregate KPI/chart either recomputed from filtered rows or snapshot-labelled,
   across **all** sections and subsections.
5. **Tests extended** (`lib/dashboard/filters.test.ts`) and a browser
   verification of filter behaviour + persistence.

## 3. Why

Acceptance criterion: *"Do not leave filters that visually appear active but do
not affect the data."* The bar renders on every filterable section (via the
section config), but coverage of the underlying data was partial. This closes
that gap section-by-section and makes non-filterable aggregates honest instead of
silently inert.

## 4. Files created

- `docs/build-reports/2026-07-21-global-filters-all-sections.md` (this file)

## 5. Files modified

Engine / shared UI:
- `apps/admin/lib/dashboard/filters.ts` — `DATE_KEYS` + `rowDate`; interface note.
- `apps/admin/components/dashboard/ui/states.tsx` — `FilteredEmptyState`,
  `SnapshotBadge`.
- `apps/admin/lib/dashboard/filters.test.ts` — +3 test groups (14 assertions).

Data:
- `apps/admin/lib/dashboard/operations-data.ts` — `city` on FacilityIssue,
  DriverPerformance, DriverIssue, OrderIssue; `city`+`channel` on Invoice.
- `apps/admin/lib/dashboard/types.ts` — `city?`/`scope?` on `SeoTask`.
- `apps/admin/lib/dashboard/mock-data.ts` — geo/scope tags on `seoTasks`.

Components (wired inert lists / recomputed or snapshot-labelled aggregates):
- Operations: `FacilityFacing.tsx`, `Drivers.tsx`, `CustomerOrders.tsx`,
  `CustomerChargesPayments.tsx`.
- `sales/Sales.tsx`, `partner-acquisition/PartnerAcquisition.tsx`,
  `seo/SeoAgents.tsx`, `marketing/Marketing.tsx`,
  `finance-compliance/FinanceCompliance.tsx`, `dev-automation/DevAutomation.tsx`,
  `app/(dashboard)/overview/page.tsx`.

Docs:
- `docs/architecture/dashboard-filter-system.md` (updated),
  `docs/checklists/internal-dashboard-ui-test-script.md` (updated),
  `docs/00-Home.md` (updated).

## 6–8. API / DB / migrations

None. Mock-only; no backend, endpoint, model or migration changes.

## 9. UI pages/components changed

Every top-level section and its subsections. New shared components
`FilteredEmptyState` and `SnapshotBadge`.

## 10. Agent behaviour / integrations

Unchanged. No LLM, WhatsApp, Stripe or external calls.

## 11. Section-by-section coverage

- **Overview** — orders/conversations/by-channel/by-city already filter; KPI grid
  + trend charts snapshot-labelled.
- **Operations / Customer Facing** — already filtered (unchanged).
- **Operations / Facility Facing** — `facilityIssues` now filters; KPI snapshot.
- **Operations / Drivers** — `driverPerformance` + `driverIssues` now filter; KPI
  snapshot.
- **Operations / Customer Orders** — `orderIssues` now filters; KPI snapshot.
- **Operations / Payments** — `invoices` now filter by city/channel; KPI snapshot.
- **Sales** — `businessAccounts` now filters (engine) with empty state;
  market/region charts cascade City→Market→Region; channel-conversion chart
  filters; overview/b2b/top-customers/conversion-funnel snapshot-labelled.
- **Partner Acquisition** — all tables already filter; market-readiness &
  outreach-conversion charts recomputed from filtered rows; team + pipeline +
  compliance + coverage + meetings aggregates snapshot-labelled.
- **SEO Agents** — geo/site-wide tables filter (`seoTasks` now geo/scope-tagged);
  overview/agent-fleet/reports labelled "Global / site-wide".
- **Marketing** — social/campaigns/influencer/PR already filter;
  overview/platform-analytics/content-calendar/approvals/UTM labelled
  "Brand-wide".
- **Finance & Compliance** — payments/refunds/compliance/documents/audit/risk
  tables filter; overview market chart cascades; overview/cost-breakdown/
  compliance-KPI aggregates snapshot-labelled. Payment privacy preserved.
- **Dev & Automation** — technical tables filter with a "Global · not
  geo-filtered" note; deployments routed through the engine (pass-through);
  overview/LLM/deployments labelled "Global / technical".
- **Reports** — already surfaces the active filter **scope** on each report
  (`filterContextLabel`); unchanged.
- **Settings** — intentionally not filtered (`filterable: false`).

## 12. What is mock-only / live

All mock. No live WhatsApp, Stripe, LLM or external calls. Filtering runs over
deterministic in-memory mock arrays.

## 13. Intentionally deferred

- URL-syncing filters (they reset on hard reload; persist across client-side nav).
- Global Status/Owner in the bar (kept local — values are domain-specific).
- A dedicated Country dropdown (folded into Market for GCC operating markets;
  engine still matches `country`).
- Re-aggregating headline KPIs/time-series to an exact scope (snapshot-labelled).

## 14. Tests run

- **Type check:** `npx tsc --noEmit` → clean (0 errors).
- **Engine tests:** `npx tsx lib/dashboard/filters.test.ts` → **45 assertions
  passed** (added alternate-date-field recognition, newly geo-tagged ops rows,
  SEO `scope:"global"` bypass).
- **Route smoke:** all changed routes return HTTP 200 on `next dev`.
- **Browser behaviour (Playwright, headless):** on `/operations/drivers`, set
  City = Dubai →
  - "Overall snapshot" badge appears;
  - Driver Issues table drops the Doha order (LK-24808), keeps Dubai (LK-24814);
  - navigate **client-side** to Customer Orders → City chip **persists**, All
    Orders table drops the Doha order (LK-24815), keeps Dubai (LK-24817);
  - **no console/page errors.**

## 15. Test results

All green. See §14.

## 16. Bugs/issues found & fixed during build

- Adding an index signature to `Filterable` (first attempt at flexible date
  reading) broke the `<T extends Filterable>` constraint for concrete row types
  (Dev/Finance). Fixed by removing the index signature and reading `DATE_KEYS`
  via a runtime cast instead.

## 17. Known limitations

- Filters are in-memory (hard reload resets them).
- Headline KPI grids / some time-series remain period snapshots (labelled).
- Date matching supports `Today` / `Last 7 days` vs a fixed mock `TODAY`; other
  ranges are open.

## 18. Security / privacy notes

- No new PII. Facility/driver views remain area/city-only. Payment views remain
  status/amount/method only — no card/CVV/bank/token/full-address fields exist
  in the data. Filtering changed no privacy surface.

## 19. Cost / LLM usage

None. No LLM or external calls.

## 20. Screens to demo

Apply **UAE → Dubai → Dry Cleaning** and walk: Overview, Operations/Customer
Orders, Operations/Drivers, Sales/Services + B2B/B2C, Partner Acquisition/
Pipeline + Market Intelligence, Marketing/Campaigns, Finance/Customer Payments +
Cost Breakdown, Dev & Automation/Deployments, SEO/Content Pipeline. Note the
"Overall snapshot" / "Global" labels on aggregates and the persistent filter
chips.

## 21. Commands to run

```
cd apps/admin
npx tsc --noEmit
npx tsx lib/dashboard/filters.test.ts
npx next dev -p 3011   # then browse the routes above
```

## 22. How to verify manually

Set City = Dubai on any Operations subsection; confirm tables narrow to Dubai,
the snapshot badge appears on KPI blocks, the chip persists as you click into
other sections, and a non-matching combination (e.g. City = Muscat on a
Dubai-only table) shows the "No records match the selected filters" empty state
with a Clear-filters button.

## 23. Next recommended step

URL-sync the filter state (query params) so a scoped view is shareable and
survives a hard reload — the one remaining gap vs. a production filter UX.
