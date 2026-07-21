# Build Report — Global filters made functional

**Date:** 2026-07-20
**App:** `apps/admin`
**Status:** ✅ Built, typechecked, built, browser-verified. Mock-only, UI-only.

---

## 1. Objective
The global filter bar (Date, Market, Region, City, Channel, Service) was
presentational. Make it **actually filter the data** on the dashboard.

## 2. What was built
- A **shared in-memory filter store** (React Context) in the dashboard layout, so
  a selection persists as you move between pages and updates every consuming view
  instantly.
- A **controlled FilterBar**: selects reflect the store, an active filter shows a
  rose highlight, and there are removable **filter chips** + a **Clear all** button.
  City options are constrained to the selected market.
- A pure **filter engine** (`lib/dashboard/filters.ts`) with predicates for every
  row type (orders, conversations, tickets, facility orders, facilities, quality
  checks, handoff, follow-ups, and order-ref rows like cancellations/changes) plus
  a `filterCategory` helper for categorical charts.
- Wiring across the data-rich pages so tables, lists and categorical charts
  re-slice live, with an empty-state when nothing matches.

## 3. Files
**New:** `lib/dashboard/filters.ts`, `components/dashboard/shell/FiltersProvider.tsx`.
**Modified:** `app/(dashboard)/layout.tsx` (wrap in `FiltersProvider`),
`components/dashboard/shell/FilterBar.tsx` (controlled + chips + clear),
`overview/page.tsx`, `sales/page.tsx`, `finance/page.tsx` (→ client, filtered),
`operations/CustomerFacing.tsx`, `operations/FacilityFacing.tsx` (tables filtered),
`seo-agents/page.tsx` (filter bar removed — data is site-wide).

## 4. Coverage (honest)
**Fully filters:**
- **Overview** — Latest Orders table, Orders-by-city / Orders-by-channel charts,
  recent conversations.
- **Operations → Customer Facing** — Customer Orders, Tickets, Order Changes,
  Cancellations, Follow-ups (tab counts update too).
- **Operations → Facility Facing** — Facility Orders, Facility Management,
  Status Updates, Quality Checks, Delivery Handoff (still PII-safe: area/city only).
- **Sales** — Sales by market/channel/region, Revenue by service, Top cities,
  Top services.
- **Finance** — Revenue by market, Profit by city.

**Intentionally not filtered:**
- **Headline KPI trend cards** stay as the overall period snapshot. The mock KPIs
  are big aggregates (e.g. "3,482 orders"), not counts of the ~12 sample rows —
  deriving them from the samples would contradict the headline numbers and look
  broken. This is a deliberate, documented choice.
- **Time-series trend charts** (orders/revenue over time) remain period views.
- **SEO Agents** — metrics are site-wide (no geo/channel/service dimension), so
  the filter bar was removed there rather than left as a dead control.
- **Marketing / Reports / Settings** — no filter bar (unchanged).

## 5. Filter semantics
- **Market** picks constrain the **City** dropdown; picking a Region clears
  Market/City so the coarser choice wins.
- **Region** matches via a market→region map; **City** matches directly and via
  city→market.
- **Date range:** only "Today" narrows the sample (to 2026-07-20); wider ranges
  pass all (the sample spans ~2 days). Documented.
- **Channel** doesn't apply to facility rows (facility work isn't channel-scoped)
  — those pass the channel filter through.
- Filters are **in-memory** (not URL-synced) — they reset on a hard reload.

## 6. Tests / checks run
- `tsc --noEmit`: **PASS** (0 errors, after relaxing an unused DataTable generic).
- `npm run build`: **PASS** — filtered pages now client-rendered; all routes build.
- **Playwright**:
  - Overview: City=Dubai → chip shows, Latest Orders → 3 rows all "Dubai";
    Clear → back to 6.
  - Operations Customer Orders: Service=Dry Cleaning → 2 rows, all Dry Cleaning.
  - Operations Facility Orders: same filter → 2 rows, all Dry Cleaning (PII-safe).
  - Filter **persists across navigation**; **0 console errors**.

## 7. Known limitations
- Headline KPI cards and time-series are not filtered (see §4).
- Filters aren't URL-shareable (in-memory).
- Actions still don't persist (separate deferred item).

## 8. Next recommended step
If shareable/bookmarkable filters are wanted, sync the store to URL search params.
Otherwise, wire a mock store so table actions (assign, approve, status) persist.
