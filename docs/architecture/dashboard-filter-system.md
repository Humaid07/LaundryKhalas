# Dashboard Filter System

How the internal dashboard's **global filters** work: one filter store, one pure
engine, structured-field matching, and consistent coverage across every
filterable section, subsection and tab.

Related: [[internal-dashboard-ui]], [[ADR-internal-dashboard-design-system]].

## Goals

- Filters (Date, Region, Market, City, Channel, Service) are **truly global**:
  set once, they apply everywhere the data has matching fields, and persist as
  you navigate between sections and into subsection pages.
- Filtering is done over **structured fields**, never by parsing display text.
- A filter that doesn't apply to a dataset **passes through** — it never wrongly
  empties a section that lacks that dimension.
- Site-wide / technical rows are explicitly **tagged global** so geo filters
  don't hide them and a section never looks broken.
- No filter is "visually active but inert": if the bar is shown, the page's data
  responds (or the page clearly labels a metric as a global/overall snapshot).

## The three pieces

### 1. Filter store — `components/dashboard/shell/FiltersProvider.tsx`

A React Context (`useFilters()`) mounted once in the dashboard layout
(`app/(dashboard)/layout.tsx`), so a selection persists across every section and
subsection route. It exposes:

- `filters` — the active `Filters` object.
- `setFilter(key, value)`, `clearFilter(key)`, `clearAll()` (alias `clear()`).
- `marketOptions` / `cityOptions` — options **cascaded** from the current
  Region → Market selection.

Cascade / dependency resets happen in `setFilter`:

- Region → Market → City is the hierarchy.
- Changing **Region** clears an incompatible Market and City.
- Changing **Market** clears a now-inconsistent City.

Not URL-synced (filters reset on a hard reload) — acceptable for the mock; URL
sync is a documented next step.

### 2. Filter engine — `lib/dashboard/filters.ts`

Pure functions, no React. The geo model is the single taxonomy:

```
Region → Market/Country → City
GCC → { UAE, Qatar, Saudi Arabia, Kuwait, Bahrain, Oman }
UAE → { Dubai, Abu Dhabi, Sharjah }   Qatar → { Doha }   … etc.
Other regions in the model: MENA, Asia, Europe, Americas.
```

Key exports:

- `applyGlobalFilters<T extends Filterable>(rows, filters)` — **the one entry
  point** every section uses. Applies all active filters to a list of structured
  rows.
- Matchers: `matchesDateRange`, `matchesRegion`, `matchesMarket`,
  `matchesCountry`, `matchesCity`, `matchesChannel`, `matchesService`,
  `matchesStatus`, `matchesOwner`.
- `getFilteredSummary(rows, filters)` → `{ total, shown, hidden, isFiltered }`.
- `getAvailableFilterOptions(rows)` — distinct structured values in a dataset.
- Cascade helpers: `marketOptionsForRegion`, `cityOptionsFor`.
- Chips/context: `activeFilterChips`, `activeFilterCount`, `filterContextLabel`
  (e.g. `"Dubai · UAE · Dry Cleaning · Today"`).

**The `Filterable` row shape** — a section's row type only needs the subset it
actually has; missing fields pass through:

```ts
interface Filterable {
  region?; market?; country?; city?;
  area?;      // "City · District" — city is derived from before the "·"
  channel?; service?; status?; owner?;
  createdAt?; date?; datetime?;   // canonical date fields
  scope?: "global" | "geo";       // "global" bypasses ALL geo dimensions
}
```

**Date fields (`DATE_KEYS`).** Rows across sections timestamp their primary event
under many names, so the Date-range filter reads the **first present** of a
priority list rather than requiring a rename to `createdAt`:

```
createdAt, date, datetime, requestedAt, raisedAt, reportedAt, queuedAt,
lastContact, lastUpdate, lastGenerated, scheduledFor, timestamp, expiry,
dueDate, due
```

`rowDate` reads these via a runtime cast, so `Filterable` needs **no** index
signature (an index signature would break the `<T extends Filterable>`
constraint for concrete row types). Add a name to `DATE_KEYS` to make a new date
field participate in the Date filter.

**Matching rules:**

- **Geo (region/market/city/country):** the engine derives region ← market ←
  city automatically, so a row carrying only `city: "Dubai"` still matches
  Region=GCC and Market=UAE. A row that carries *no* geo signal passes through
  every geo filter. A row with `scope: "global"` bypasses every geo filter.
- **Channel / Service / Status / Owner:** if the row doesn't have the field, it
  passes through; otherwise it must equal the selected value.
- **Date:** open ranges (`Last 30 days`, `This quarter`, `Year to date`, empty)
  don't narrow; `Today` / `Last 7 days` compare against a fixed `TODAY` mock
  date; rows with no date pass through.

### 3. Filter UI

- **Global bar** — `components/dashboard/shell/FilterBar.tsx`, rendered by the
  page header (`ResponsivePageHeader showFilters`). Custom rounded `FilterSelect`
  dropdowns (no native `<select>`), rose active states, dark-mode + mobile ready,
  active chips + Clear all.
- **Where it shows** — centralised via the section config
  (`lib/dashboard/sections.ts`): each `SectionDef` has `filterable?: boolean`
  (default **true**). `SectionLanding` and `SubsectionShell` read it and show the
  global bar on the landing page **and** every subsection page automatically. A
  page may still pass an explicit `showFilters` override. Settings is
  `filterable: false`.
- **Local filters** — `components/dashboard/ui/LocalFilters.tsx`, for
  section-specific **non-geo** dimensions (partner type, pipeline stage, agent
  severity, environment, approval status, platform, …). These live *alongside*
  the global bar: a page applies `applyGlobalFilters` first, then its local
  filters.

## Empty states

Every filtered table/list renders a clean empty state when nothing matches. Two
shared helpers live in `components/dashboard/ui/states.tsx`:

- **`FilteredEmptyState`** — names the active filter context
  (`filterContextLabel`) and offers a one-click **Clear filters** button
  (`clearAll`). Used where a page can wire the clear action (e.g. Operations
  tabs, Sales B2B accounts).
- Plain `EmptyState` (`icon={SearchX}`, "No records match the selected filters")
  where a static block is enough.

No stale, unfiltered rows are shown while filters are active. Panel subtitles
show `shown of total` counts.

## Snapshot vs. filtered (headline KPIs & aggregate charts)

Row-level tables/lists **re-slice** under the filters. Headline KPI grids and
some time-series/donut charts are **period aggregates** with no row-level geo,
so they can't be honestly recomputed to an exact geo/date scope. The rule
(per spec): make a metric filter-aware when it derives from a filterable row set;
otherwise label it a snapshot — never leave it silently inert.

- **`SnapshotBadge`** (`states.tsx`) renders a small **"Overall snapshot"** pill
  **only while filters are active**, so the UI never implies a headline number
  responds to the scope when it doesn't. Section-specific variants use labels
  like **"Global / site-wide"** (SEO), **"Brand-wide"** (Marketing) and
  **"Global / technical"** (Dev & Automation).
- Charts that *do* derive from a filtered table are recomputed from the filtered
  rows (e.g. Partner market-readiness and outreach-conversion charts; Sales
  channel-conversion; the market/region breakdowns cascade from a selected
  City → parent Market/Region).

## Section coverage

| Section | Global filters | Notes |
|---|---|---|
| Overview | ✅ orders, conversations, city/channel charts | KPI trend cards = period snapshot |
| Operations · Customer Facing | ✅ conversations, tickets, changes, cancellations, follow-ups | urgency/status stay local |
| Operations · Facility Facing | ✅ facility orders, QC, issues, handoff | privacy: area/city only |
| Operations · Drivers | ✅ zones, pickup/delivery queues, **performance, issues** | issues/performance now carry `city`; area-only privacy |
| Operations · Customer Orders | ✅ all/active/completed/cancelled/**issues**/changes | order issues now carry `city`; order + payment status local tabs |
| Operations · Payments | ✅ overview, pending, refunds, adjustments, issues, **invoices** | B2B invoices now carry `city` + `channel` |
| Sales | ✅ markets, channels, services, cities | headline KPIs = snapshot |
| Partner Acquisition | ✅ pipeline, market intel, outreach, meetings, compliance, coverage, performance | type/stage/owner stay local |
| SEO Agents | ✅ hyperlocal/area/city pages, geo-tagged content/GSC/competitor rows | site-wide metrics tagged `scope:"global"` |
| Marketing | ✅ campaigns/posts/calendar/UGC/PR/UTM by city/service/date | platform + approval status stay local |
| Finance & Compliance | ✅ payments, refunds, facility/driver compliance, documents, audit, risk | payment privacy preserved |
| Dev & Automation | ✅ market/channel/service-specific technical rows | generic technical rows tagged `scope:"global"` |
| Reports | ✅ shows active-filter **scope** context on each report | figures are period aggregates (labelled) |
| Settings | ⛔ `filterable: false` | workspace config is not geo-scoped |

## Global vs. site-wide rows

Sections that mix geo-specific and site-wide data (SEO, Dev & Automation,
Marketing brand campaigns) tag their genuinely global rows with
`scope: "global"`. Those rows stay visible under any geo selection, so choosing
`City = Dubai` never makes SEO or Dev & Automation look empty/broken — only the
truly market-specific rows drop out when they don't match.

## Testing

- Pure-engine assertions: `lib/dashboard/filters.test.ts`
  (`npx tsx lib/dashboard/filters.test.ts`) — region/market/city/channel/
  service/date matching, the Region→Market→City cascade, dimension pass-through,
  `scope:"global"` bypass, and empty-result behaviour.
- Type safety: `npx tsc --noEmit`.
- Manual/browser: apply UAE → Dubai → Dry Cleaning and walk the sections
  (see `docs/checklists/internal-dashboard-ui-test-script.md`).

## Design decisions & limitations

- **Global bar dimensions:** Date, Region, Market, City, Channel, Service. This
  is deliberate.
  - **Status & Owner are *local* filters, not global.** Their values are
    domain-specific per section (payment status ≠ order status ≠ compliance
    status), so a single global Status would wrongly empty unrelated tables. The
    engine keeps `matchesStatus`/`matchesOwner` for local/typed use; the global
    bar never sets them.
  - **Country** is folded into Market for the GCC operating markets (country ==
    market there), so the bar shows Market rather than a redundant Country
    dropdown. The engine still matches a row's `country` field
    (`matchesCountry`).
- Filters are in-memory (reset on **hard reload**; they persist across
  client-side navigation); no URL sync yet.
- Headline KPI grids and some time-series/donut charts remain period snapshots,
  explicitly labelled via `SnapshotBadge`. Tables, lists, categorical charts and
  table-derived charts do re-slice.
- Date matching supports `Today` / `Last 7 days` against a fixed mock `TODAY`;
  other ranges are treated as open.
