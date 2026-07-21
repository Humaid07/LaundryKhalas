# Architecture — Dashboard Information Architecture

**App:** `apps/admin` (Next.js 14 App Router) · route group `(dashboard)` · mock-only
**Pattern established:** 2026-07-21 · **rolled out to every section:** 2026-07-21

## Why landing + subsection

Several top-level sections had grown into single pages stacking 9–14 KPIs, 8+
charts and up to 10 tab strips (Sales, Partner Acquisition, SEO Agents,
Marketing, Finance & Compliance, Dev & Automation, Reports). That is the
"15 tables on one page" problem. Operations was the first section refactored into
a **landing page + focused subsection routes** (see
[[2026-07-21-operations-subsection-pages]]); this document records the same
pattern applied across the **entire** dashboard.

The rule now holds for every domain:

> A top-level section is a **command hub** (landing page = summary + navigation).
> Each subsection is its **own focused route** (the heavy tables/charts/tools).

## The shared machinery

One config drives every landing page, every breadcrumb and every sub-nav — no
per-section wiring.

| Piece | File | Role |
| --- | --- | --- |
| `SECTIONS` registry | `lib/dashboard/sections.ts` | Single source of truth: for each section — base route, header copy, card grid density, and the ordered list of subsections (slug, label, description, icon, summary KPIs, status badge). |
| `SectionLanding` | `components/dashboard/section/SectionLanding.tsx` | Renders a section's landing page: `ResponsivePageHeader` + a responsive grid of `SectionCard`s. Summary/navigation only — **no heavy data**. |
| `SectionCard` | `components/dashboard/section/SectionCard.tsx` | One subsection card: icon, title, description, 2–4 KPI chips, optional status badge, hover lift, rose accent, "Open →". Links to `${base}/${slug}`. |
| `SubsectionShell` | `components/dashboard/section/SubsectionShell.tsx` | Wraps every subsection page: `SectionSubNav` (breadcrumb + pills) + focused `ResponsivePageHeader` (title/description from config) + `{children}`. `showFilters` opts a page into the global filter bar. |
| `SectionSubNav` | `components/dashboard/section/SectionSubNav.tsx` | Breadcrumb (`Section / Subsection`) + a scrollable pill row of the section's subsections, active state from `usePathname()`. Config-driven, works for every section. |
| Content routers | `components/dashboard/<section>/<Section>.tsx` | One `…Subsection({ slug })` component per section renders the focused content for a slug (a `switch`, or a data lookup for Reports). Reuses the existing StatGrid/ChartCard/DataTable/Panel primitives and mock data. |

### A subsection route file is tiny and uniform

```tsx
// app/(dashboard)/sales/markets/page.tsx
import { SubsectionShell } from "@/components/dashboard/section/SubsectionShell";
import { SalesSubsection } from "@/components/dashboard/sales/Sales";

export default function Page() {
  return (
    <SubsectionShell sectionKey="sales" slug="markets" showFilters>
      <SalesSubsection slug="markets" />
    </SubsectionShell>
  );
}
```

The landing page is just `<SectionLanding sectionKey="sales" />`.

## Full route map (10 landings + 73 subsections = 83 routes)

Sidebar shows **only the 10 top-level items** (`lib/dashboard/nav.ts`). Subsections
are reached via landing cards, breadcrumbs, and the in-section pill sub-nav. The
sidebar keeps the parent highlighted on every sub-route (`pathname.startsWith`).

```
/overview                         (executive command center — no subsections; cards deep-link out)

/operations                       → Customer Facing · Facility Facing · Drivers · Customer Orders
  /customer-facing /facility-facing /drivers /customer-orders

/sales                            → Overview · Markets · Channels · Services · B2B/B2C · Top Customers · Conversion Funnel
  /overview /markets /channels /services /b2b-b2c /top-customers /conversion-funnel

/partner-acquisition              → Team · Pipeline · Market Intelligence · Outreach · Meetings · Compliance Queue · Regional Coverage · Performance Preview
  /team /pipeline /market-intelligence /outreach /meetings /compliance-queue /regional-coverage /performance-preview

/seo-agents                       → Overview · Agent Fleet · GSC Performance · Indexing · Content Pipeline · Hyperlocal Pages · Technical SEO · Competitors · AI Search · Reports
  /overview /agent-fleet /gsc-performance /indexing /content-pipeline /hyperlocal-pages /technical-seo /competitors /ai-search /reports

/marketing                        → Overview · Platform Analytics · Content Calendar · Creative Studio · Social Posting · Campaigns · Approvals · Influencer/UGC · PR & Outreach · UTM Tracking
  /overview /platform-analytics /content-calendar /creative-studio /social-posting /campaigns /approvals /influencer-ugc /pr-outreach /utm-tracking

/finance-compliance               → Financial Overview · Cost Breakdown · Customer Payments · Refunds & Adjustments · Partner/Facility Compliance · Driver Compliance · Documents & Expiry · Audit Trail · Risk Flags
  /financial-overview /cost-breakdown /customer-payments /refunds-adjustments /partner-facility-compliance /driver-compliance /documents-expiry /audit-trail /risk-flags
  (/finance → 307 redirect to /finance-compliance)

/dev-automation                   → Overview · Agent Health · Technical Issues · API & Webhook Health · Job Queue · LLM/Cost Usage · Deployments · Integration Status · Logs & Audit
  /overview /agent-health /technical-issues /api-webhook-health /job-queue /llm-cost-usage /deployments /integration-status /logs-audit

/reports                          → Daily Standup · Operations · Sales · Partner Acquisition · SEO · Marketing · Finance & Compliance · Dev & Automation · Monthly Executive
  /daily-standup /operations /sales /partner-acquisition /seo /marketing /finance-compliance /dev-automation /monthly-executive

/settings                         → Profile & Team · Roles & Permissions · Markets · Notifications · Agent Guardrails · Connected Apps · Theme
  /profile-team /roles-permissions /markets /notifications /agent-guardrails /connected-apps /theme
```

## Filters: global vs local per section

- **Global geo/service/channel filter bar** (`FilterBar` + `FiltersProvider`) is
  opted-in per subsection page via `SubsectionShell showFilters`. Applied where
  geo slicing is meaningful: **Overview, Operations, Sales, Finance &
  Compliance** subsections.
- **Local filters** (`ui/LocalFilters.tsx`) stay inside sections whose data is not
  GCC-geo-shaped: **SEO Agents** (agent status / page type / issue type),
  **Dev & Automation** (status / mode / severity / owner), **Partner Acquisition**
  (region / type / owner / stage). Reports and Settings need neither.

## Privacy / security (unchanged, preserved by the move)

The refactor only relocated existing content into focused routes; every firewall
rule is intact.

- **Facility Facing / Drivers** — area/city only, no customer name/phone/email/
  address; "Privacy firewall on" banner retained.
- **Customer-facing lists** — `maskPhone()` on every number.
- **Finance & Compliance** — payment views show amount/method label/status/order
  id only; never card, CVV or bank details.
- **Dev & Automation → Logs & Audit** — safe events only (event/module/severity/
  trace id); no secrets, tokens or raw env values. "No secrets" status badge.
- **Partner Acquisition** — business-level data only.
- Every agent/risky action stays **mock-only + approval-gated**; mock/staged
  state is always visible.

## What is mock-only / deferred

- All data is deterministic mock (`lib/dashboard/*-data.ts`), no live APIs, no
  fetching, no secrets. Server components import mock data and render client
  leaves (charts, tabs, theme toggle).
- Export / share buttons on landing and report pages are **placeholders**.
- Swapping mock for a real API later = replace the `lib/dashboard/*-data.ts`
  reads with server fetches; props are already typed (`lib/dashboard/types.ts`).

Related: [[internal-dashboard-ui]] · [[2026-07-21-operations-subsection-pages]] ·
[[2026-07-21-dashboard-subsection-architecture]] ·
[[ADR-internal-dashboard-design-system]] · [[privacy-firewall]]
