# Minimal Dashboard Design System

> Status: **active** · Introduced 2026-07-23 · Applies to the command-center dashboard (`apps/admin`, `app/(dashboard)/**`). Does **not** apply to the legacy `/admin` pages.

The dashboard was redesigned to be **minimal, spacious, and easy to understand**. Main pages were dense — many cards, many fields per card, many badges, drawers as the primary detail surface. This system fixes that with one rule and a small shared component library.

## The core rule

> **The Overview page can be information-rich. Every other main page is minimal.**

Progressive disclosure everywhere else:

| Layer | Shows |
|-------|-------|
| **Main page** | A light summary: a compact KPI strip, workflow/status tabs, and a scannable list of records. |
| **Card / row** | A short preview — an id, a title, one status badge, **2–3 fields max**. No actions. |
| **Detail page** | The full record: every field, lifecycle, related data — and **all actions**. |

If you're tempted to add a fourth field to a card, a second badge, or an action button on a main page — it belongs on the detail page instead.

## Design inspiration

- **Linear** — the sidebar, generous spacing, calm hierarchy, muted inactive states, progressive disclosure.
- **Stripe Dashboard** — professional detail pages, clean tables, grouped information, subtle status/action patterns.
- **Vercel / shadcn** — minimal cards, clean typography, modern admin structure.

These are inspiration, not templates. The look stays LaundryKhalas: warm rose-white / deep-slate surfaces, "pink is a signal, not a fill."

## Dashboard hierarchy (every page)

1. **Sidebar** — navigation (which section / subsection). Nested, from `sections.ts`.
2. **Page header** — title + one short explanation + at most one primary action.
3. **Workflow tabs** — status/workflow filters for the *current page only* (never navigation to another subsection — that lives in the sidebar).
4. **Main content** — a minimal KPI strip + a list/table of light record previews.
5. **Detail page** — full information and all actions.

## The 15 design rules

1. Increase spacing between cards and sections (`space-y-6` content rhythm; `gap-6` in detail grids).
2. Fewer cards on main screens.
3. Fewer colors — value text stays ink; tone is used only when it signals attention.
4. Subtle borders (`border-border/70`) and soft backgrounds (`bg-surface`, `bg-surface-2`).
5. Stronger typography hierarchy (display title → muted description → eyebrow labels).
6. Muted secondary text (`text-ink-muted`, `text-ink-faint`).
7. Avoid badge clusters — **one** status badge per card.
8. Avoid long descriptions on cards.
9. **2–3 key fields per card, max.**
10. Full details live inside detail pages.
11. Actions live **only** inside detail pages.
12. Clean empty states (`EmptyState`).
13. Skeleton loading where useful (`Skeleton`, `LoadingState`).
14. Dark mode stays premium and readable (token-driven; both themes covered).
15. Responsive mobile/tablet layouts (lists collapse gracefully; tables → labeled cards under `md`).

## The shared component library

Location: `apps/admin/components/dashboard/minimal/` · import everything from the barrel:

```ts
import {
  MinimalPageHeader, MinimalKpiStrip, WorkflowTabs,
  CompactRecordCard, RecordList, DataPreviewTable, ViewDetailsButton,
  DetailPageShell, DetailColumns, DetailSectionCard, Field, FieldGrid, Chip,
  ActionMenu, StatusBadge, EmptyState, LoadingState, Skeleton, SnapshotBadge,
} from "@/components/dashboard/minimal";
```

| Component | Role |
|-----------|------|
| `MinimalPageHeader` | Calm page top: eyebrow, title, one-line description, single primary action. |
| `MinimalKpiStrip` | Quiet KPI row — label + number only, no sparklines/hover. Keep to **3–4** KPIs. `MinimalKpi = {label, value, hint?, tone?}`. |
| `WorkflowTabs` | Status/workflow filter pills for the current page. `{id, label, count?}[]`. (Canonical source re-exported from the Operations workspace.) |
| `CompactRecordCard` | The click-through record preview: id, title, one status badge, **≤3 fields**, optional `meta`, a chevron. `href` **or** `onClick`; neither ⇒ static preview (no chevron). Never carries actions. |
| `RecordList` | Vertical list wrapper (default main-page record layout — calmer than a card grid). |
| `DataPreviewTable` | Calm, click-through table for metric-heavy previews. Rows open a detail via `rowHref`/`onRowClick`. Responsive → labeled cards under `md`. No inline row actions. |
| `ViewDetailsButton` | The explicit "there's more inside" affordance. |
| `DetailPageShell` | Detail-page frame: back link → title + status + actions → children. Where the heavy info + **all actions** live. |
| `DetailColumns` | Stripe-style two-column body: wide main column + sticky sidebar. |
| `DetailSectionCard` / `Field` / `FieldGrid` / `Chip` | Grouped topic blocks and label/value pairs on detail pages. |
| `ActionMenu` | Overflow menu for record actions (detail pages only). Approval-gated items are labelled (`approval: true`, RULE 13). |
| `StatusBadge` | One-tone status chip (canonical source re-exported from `ui/primitives`). |
| `EmptyState` / `LoadingState` / `Skeleton` / `SnapshotBadge` | States (canonical source re-exported from `ui/states`). |

### Routing: prefer full detail pages over drawers

Cramped 480px side drawers are **removed as the primary detail surface**. Important records open a dedicated route:

```
/operations/customer-orders/[orderId]
/operations/facility-facing/orders/[orderId]
/operations/drivers/[driverId]
/operations/customer-facing/tickets/[ticketId]
/seo-agents/runs/[runId]          (and similar per section)
/marketing/campaigns/[campaignId]
/finance-compliance/customer-payments/[orderId]
/dev-automation/job-queue/[jobId]
/reports/[reportId]
```

Each detail route is a **server component** that reads the id (and originating `?tab=`) from the route, resolves the record via a pure getter in the section's `*-data.ts`, and renders a `DetailPageShell`. "Back" returns to the exact tab the operator came from. A not-found state is always handled.

The Customer-Facing WhatsApp inbox and the two-pane chat workspace are kept as-is — they are already the right "full workspace" experience for a conversation.

## Reference implementation

Operations is the canonical example — mirror it when building any section:

- Minimal main page: `components/dashboard/operations/CustomerOrders.tsx`, `FacilityFacing.tsx`, `Drivers.tsx`, `CustomerFacing.tsx`
- Full detail page + getter: `components/dashboard/operations/facility-detail/{FacilityOrderDetailPage.tsx,data.ts}`
- Detail route: `app/(dashboard)/operations/facility-facing/orders/[orderId]/page.tsx`

## What is kept (do not change)

- Existing routes, the nested sidebar, workflow tabs, global filters (`FiltersProvider`/`FilterBar`), and dashboard data contracts.
- Backend API structure and the live API clients.
- `sections.ts` remains the config spine for landing cards, sub-nav, and page headers.

## What is mock-only

All record data on these pages is deterministic mock data. No action performs a live effect (no live WhatsApp, Stripe, or LLM). Approval-gated actions are labelled but inert in mock mode.
