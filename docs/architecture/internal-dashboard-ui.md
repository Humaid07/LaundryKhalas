# Architecture — Internal Dashboard UI

**App:** `apps/admin` (Next.js 14 App Router, TypeScript, Tailwind) · port 3000
**Added:** 2026-07-20 · mock-only

## Where it lives

The internal dashboard is built **inside the existing `apps/admin` app** (not a
new app), per the "extend, don't duplicate" rule. It is isolated in a route
group so the legacy WhatsApp-ops admin keeps working untouched.

```
apps/admin/
  app/
    layout.tsx              # root: fonts (next/font) + ThemeProvider + QueryProvider
    page.tsx                # redirect("/overview")
    globals.css             # CSS-variable design tokens (light + dark)
    (dashboard)/            # NEW command center (route group — no URL segment)
      layout.tsx            # <AppShell>
      overview|operations|sales|partner-acquisition|seo-agents|marketing|
        finance-compliance|dev-automation|reports|settings/page.tsx  # 10 sections
    admin/                  # LEGACY pages (unchanged, still build)
  components/dashboard/
    shell/                  # AppShell, Sidebar, Topbar, FilterBar, ThemeToggle, PageHeader, Brand
    ui/                     # Panel, StatCard, ChartCard, DataTable, Button, Tabs, Switch, states, tones, LocalFilters…
    operations/            # Customer/Facility/Drivers/Payments tab components
    partner-acquisition/   # PartnerAcquisition (role cards, pipeline, 7 tabs)
    dev-automation/        # DevAutomation (agent health, 9 tabs)
    charts.tsx              # Recharts wrappers (client)
    widgets.tsx             # Agent/Approval/Timeline/Report/Platform/Finance cards
    CreativeStudio.tsx      # interactive mock AI creative composer
  lib/dashboard/
    nav.ts                 # sidebar sections (10)
    types.ts               # shared domain types
    formatters.ts          # currency/number/percent/relative-time, maskPhone
    chart-theme.ts         # chart colors (CSS-var backed) + tooltip styles
    status-maps.ts         # domain status → tone
    filters.ts             # global (geo) filter engine
    mock-data.ts           # core mock data (deterministic, LaundryKhalas-specific)
    operations-data.ts     # operations (customer/facility/drivers/payments) mock data
    partner-acquisition-data.ts  # partner pipeline, market intel, compliance, coverage
    finance-compliance-data.ts   # compliance/risk mock data (extends finance analytics)
    dev-automation-data.ts       # agents, issues, APIs, jobs, LLM, deploys, integrations, logs
    theme-provider.tsx     # next-themes wrapper (class strategy)
```

## Top-level sections (10)

`Overview · Operations · Sales · Partner Acquisition · SEO Agents · Marketing ·
Finance & Compliance · Dev & Automation · Reports · Settings`

- **Partner Acquisition** (`/partner-acquisition`) — partnership/BD command center:
  4 role cards, 12 KPIs, 8 charts, 7 tabs (pipeline · market intelligence · outreach ·
  meetings · compliance queue · regional coverage · performance preview). Uses **local**
  filters (Region/Type/Owner/Stage) because partner data is worldwide, not GCC-only.
- **Finance & Compliance** (`/finance-compliance`, was `/finance`) — finance analytics
  **plus** compliance/risk: 13 financial + 10 compliance KPIs, 9 tabs (financial overview ·
  cost breakdown · customer payments · refunds & adjustments · facility compliance · driver
  compliance · documents & expiry · audit trail · risk flags). `/finance` → 307 redirect
  (in `next.config.js`).
- **Dev & Automation** (`/dev-automation`) — technical ops: 14 KPIs, 8 charts, 9 tabs
  (automation overview · agent health · technical issues · API/webhook health · job queue ·
  LLM/cost usage · deployments · integration status · logs & audit). Local filters
  (Status/Category/Mode/Owner).

**LocalFilters** (`ui/LocalFilters.tsx`): a self-contained, in-memory filter bar
(`useLocalFilters` hook + `LocalFilterBar` + `matchesLocal` helper) for sections where the
global geo FilterBar doesn't cleanly apply. Same visual language as the global bar.

## Design system

- **Tokens as CSS variables** (`globals.css`): every semantic color is an
  `R G B` triplet so Tailwind `<alpha-value>` utilities (`bg-rose/10`) work and
  values swap between `:root` and `.dark`.
- **Tailwind** maps tokens via `rgb(var(--x) / <alpha-value>)`. Legacy tokens
  (`brand`, `neutral`, `*-soft`, `*-text`) preserved as static aliases.
- **Rose is a signal**, not a fill (brand, active nav rail, primary buttons,
  hero chart hue). Categorical chart palette: rose → plum → teal → amber → sky → slate.
- **Type trio:** Bricolage Grotesque (display) · Plus Jakarta Sans (body) ·
  Space Grotesk (numeric/tabular). Loaded via `next/font` (self-hosted).
- **Dropdowns are custom, never native.** `ui/FilterSelect.tsx` is the single
  reusable select — a dependency-free listbox (`combobox`/`listbox`/`option`
  roles) with rounded-full pill triggers, a `rounded-2xl` `surface-raised`
  popover (`lk-menu-in` animation, right-edge auto-flip, viewport-capped width),
  rose active/selected state + check, rose focus ring (no native blue outline),
  and full keyboard/outside-click/Escape support. Used by **both** the global
  `FilterBar` and the `LocalFilterBar`. See
  [[2026-07-21-filter-dropdown-redesign]].

## Theming

`next-themes` with `attribute="class"`, default light. `ThemeToggle` flips
`.dark` on `<html>`. Because chart colors are `rgb(var(--c-*))`, charts recolor
with the theme automatically — no JS re-read needed. `suppressHydrationWarning`
on `<html>` avoids the theme-class hydration warning.

## Responsiveness

- **Desktop (lg+):** fixed sidebar (collapsible to icon rail), rich multi-column grids.
- **Tablet (md):** 2-column grids; sidebar collapsible.
- **Mobile (< lg):** sidebar becomes an off-canvas drawer (overlay + Escape +
  scroll-lock); `DataTable` renders labeled **cards** instead of a table; tab
  strips scroll horizontally.

## Data flow

Pages are **server components** that import deterministic mock data and render
client leaves (`charts.tsx`, `Tabs`, `ThemeToggle`, `CreativeStudio`, `Switch`).
No fetching, no state persistence. Swapping mock data for a real API later means
replacing `lib/dashboard/mock-data.ts` reads with server fetches — component
props are already typed for it (`lib/dashboard/types.ts`).

## Landing + subsection architecture (all sections)

Every top-level section now follows the Operations pattern: a **landing page of
subsection cards** plus **dedicated focused subsection routes** — never one
crowded page. This is driven by a single config, `lib/dashboard/sections.ts`
(`SECTIONS`), and four reusable components: `section/SectionLanding.tsx`,
`section/SectionCard.tsx`, `section/SubsectionShell.tsx`,
`section/SectionSubNav.tsx`. Each section has one content router
(`<section>/<Section>.tsx` → `…Subsection({ slug })`) that renders the focused
content per slug, reusing existing charts/tables/panels + mock data. **10 landing
pages + 73 subsection routes = 83 routes.** The sidebar stays at **10 top-level
items only**; subsections are reached via landing cards, breadcrumbs and the
in-section pill sub-nav (parent stays active on sub-routes). Full route map and
machinery: [[dashboard-information-architecture]]. See
[[2026-07-21-dashboard-subsection-architecture]].

## Operations: landing + four subsection pages

To keep Operations scalable and uncluttered, `/operations` is a **landing page**
and each area is its **own route** (not one crowded tab strip):

```
/operations                   → OperationsLanding.tsx (4 section cards)
/operations/customer-facing    → CustomerFacing.tsx
/operations/facility-facing    → FacilityFacing.tsx
/operations/drivers            → Drivers.tsx
/operations/customer-orders    → CustomerOrders.tsx   (order center)
```

- **OperationsLanding.tsx** — four large cards (icon, description, 3-KPI summary,
  status badge, hover, "Open section" link). No heavy data on the landing.
- **OperationsSubNav.tsx** — breadcrumb (`Operations / <Section>`) + scrollable
  pill nav shown on each subsection page. `OPERATIONS_SUBSECTIONS` is the single
  source of truth. Sidebar keeps one **Operations** item; active-state still
  highlights it on all sub-routes (`startsWith`).
- **CustomerFacing.tsx** — tabs: WhatsApp Agent (live console), **Conversations**
  (masked, no phone column), Tickets / Concerns, Cancellations, Order Changes,
  Follow-ups. 8 KPIs incl. Refund Requests.
- **FacilityFacing.tsx** — tabs: Facility Orders, Facility Assignment, Status
  Updates, Issues, Quality Checks, Delivery Handoff. Privacy firewall banner +
  area/city only.
- **Drivers.tsx** — pickup/delivery fleet. 10 KPIs; tabs: Driver Overview,
  Pickup/Delivery Queue, Performance, Issues. Queues show **area/city only**.
- **CustomerOrders.tsx** — dedicated order center (distinct from support). 10
  KPIs; tabs: All Orders, Active, Completed, Cancelled, Orders With Issues, Order
  Changes. Global filter bar **+ local** Order Status & Payment Status filters.
  Reads the shared `orders` mock; prepared (not wired) for `/api/orders/*`.

Payments are **no longer an Operations subsection** — they live in Finance &
Compliance, with payment-status columns surfaced in Customer Orders.
`CustomerChargesPayments.tsx` is preserved in the tree but unrouted.

Each subsection has its own KPI row, filter bar, tables, activity timeline and
quick-actions panel. Mock data + tone maps live in
`lib/dashboard/operations-data.ts`; filter predicates in
`lib/dashboard/filters.ts`. See [[2026-07-21-operations-subsection-pages]].

> **Deterministic relative time:** `formatRelativeTime` computes against a fixed
> `MOCK_NOW` (2026-07-20T10:00Z), not real `Date.now()`. This keeps statically
> prerendered relative strings identical to client hydration (no React #425
> hydration text mismatch) and makes the mock timeline read consistently.

## Global filters

The filter bar (Date/Market/Region/City/Channel/Service) is backed by a shared
in-memory store: `FiltersProvider` (React Context) in the dashboard layout, read
via `useFilters()`. `FilterBar` is controlled (active chips + Clear; Market
constrains City) and renders each control with the custom `FilterSelect`
dropdown (see Design system). Pure predicates live in `lib/dashboard/filters.ts`. Pages that
filter (Overview, Operations both teams, Sales, Finance) are client components
that re-slice their tables/lists and categorical charts reactively. Headline KPI
trend cards and time-series stay as period snapshots (the mock KPIs are
aggregates, not counts of the sample rows). SEO Agents has no filter bar (metrics
are site-wide). See [[2026-07-20-global-filters-functional]].

## Privacy

`maskPhone()` masks numbers in all customer-facing lists; no full addresses are
rendered; every agent action is shown behind a human approval gate; mock-mode is
always visible (sidebar badge + Settings chips).

**Facility Facing enforces the privacy firewall by construction:** its records
(`operations-data.ts`) carry no customer identity — **area/city only** (no name,
phone, email, full address or complaint notes). A "Privacy firewall on" banner is
always shown on the Facility tab. See
[[ADR-operations-customer-facing-facility-facing]].

**Drivers** show customer **area/city only** in queues (full address deferred to
a future authorized detail view) — same "Privacy firewall on" banner.
**Customer Charges / Payments** shows customer name (the ops team's customer
view, consistent with Customer Orders) but **never** card number, CVV, bank
details or unmasked phone — amount, method label, status, order id and area only.

Related: [[admin-ui-architecture]] · [[standalone-whatsapp-agent]] ·
[[ADR-internal-dashboard-design-system]] · [[privacy-firewall]]
