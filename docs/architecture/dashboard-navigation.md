# Dashboard Navigation — Architecture

**Status:** Live · **Last updated:** 2026-07-22

The admin command center uses a **three-layer** navigation model:

1. **Left sidebar** — hierarchical primary navigation (section → subsection).
2. **Page-level top tabs** — workflow tabs *within* a page (e.g. Driver Overview /
   Pickup Queue / Delivery Queue on the Drivers page).
3. **Content area** — only the selected page's data.

This document covers layer 1 (the sidebar) after the nested-navigation refactor.

---

## 1. The nav tree (single source of truth)

`apps/admin/lib/dashboard/nav.ts` defines `NAV_ITEMS: NavItem[]`. Each item:

```ts
type NavChild = { label: string; href: string; badge?: number };
type NavItem = {
  label: string;
  href: string;            // parent landing/overview route
  icon: LucideIcon;
  description: string;
  badge?: number;          // aggregated parent count
  children?: NavChild[];   // nested sub-tabs (existing routes)
  defaultOpen?: boolean;   // expand even when route is elsewhere
  allowedRoles?: string[]; // reserved for future role-gating
};
```

**Children are derived from `sections.ts`**, not hand-maintained:

```ts
function childrenOf(sectionKey, base) {
  return subsectionsOf(sectionKey).map((s) => ({
    label: s.label, href: `${base}/${s.slug}`, badge: s.badge,
  }));
}
```

So the sidebar tree can never drift from the actual routes — `sections.ts`
(`SECTIONS[key].subsections`) is the one place subsections are declared, and both
the sidebar and each section's in-page sub-nav read from it. Every child `href`
(`/operations/customer-facing`, `/seo-agents/agent-fleet`, …) already exists as a
real route under `app/(dashboard)/`.

### Which sections have children

| Parent | Children |
|---|---|
| Overview | *(none — single page)* |
| Operations | Customer Facing, Facility Facing, Drivers, Customer Orders |
| Sales | Overview, Markets, Channels, Services, B2B/B2C, Top Customers, Conversion Funnel |
| Partner Acquisition | Team, Pipeline, Market Intelligence, Outreach, Meetings, Compliance Queue, Regional Coverage, Performance Preview |
| SEO Agents | Overview, Agent Fleet, GSC Performance, Indexing, Content Pipeline, Hyperlocal Pages, Technical SEO, Competitors, AI Search, Reports |
| Marketing | Overview, Platform Analytics, Content Calendar, Creative Studio, Social Posting, Campaigns, Approvals, Influencer/UGC, PR & Outreach, UTM Tracking |
| Finance & Compliance | Financial Overview, Cost Breakdown, Customer Payments, Refunds & Adjustments, Partner/Facility Compliance, Driver Compliance, Documents & Expiry, Audit Trail, Risk Flags |
| Dev & Automation | Overview, Agent Health, Technical Issues, API & Webhook Health, Job Queue, LLM/Cost Usage, Deployments, Integration Status, Logs & Audit |
| Reports | Daily Standup, Operations, Sales, Partner Acquisition, SEO, Marketing, Finance & Compliance, Dev & Automation, Monthly Executive |
| Settings | Profile & Team, Roles & Permissions, Markets, Notifications, Agent Guardrails, Connected Apps, Theme |

## 2. Rendering & behavior (`Sidebar.tsx`)

- **`ParentRow`** — the section link + an expand/collapse chevron button (a sibling
  of the link, so clicking the label still navigates to the section landing).
- **`ChildRow`** — an indented sub-tab under a left guide-line, with a dot marker
  and optional count badge.
- **Expansion state** — `useState<boolean | null>(null)` per parent. Effective
  expanded = `userToggle ?? (routeInSection || defaultOpen)`, so the section
  containing the current route **auto-expands**, and a user toggle then wins.

### Highlighting (dual)

| condition | parent | child |
|---|---|---|
| on the section landing (`pathname === href`) | **filled** rose + rail | — |
| on a child route (`pathname` startsWith `href/`) | rose text (highlighted, not filled) | **filled** rose + rail on the active child |
| elsewhere | muted | muted |

This keeps the **parent highlighted while inside any child** (route-prefix match)
while the **active child gets the strong filled treatment** so the current page
reads unambiguously.

### Collapsed & mobile

- **Collapsed** (desktop, `lk-sidebar-collapsed` in localStorage) → icon-only rail;
  children and chevrons are hidden; the active section's icon is highlighted;
  clicking navigates to the section landing.
- **Mobile** → the drawer renders the same `Sidebar` with `collapsed={false}`, so
  the full nested tree is available; `onNavigate` closes the drawer on click.

## 3. Badges

- **Parent badge** = aggregated "needs attention" count (hardcoded in `NAV_ITEMS`,
  e.g. Operations `6`).
- **Child badge** = subsection-specific count from `sections.ts`
  (`Subsection.badge`, e.g. Customer Facing `7`, Drivers `12`, Customer Orders `82`).

Badges are illustrative mock values today; wiring them to live counts is a
follow-up (a single aggregation helper feeding both levels).

## 4. Section landing pages

Navigation no longer depends on landing pages. `/operations` is now a clean
**Operations Overview** (`OperationsOverview.tsx`): a KPI row, an urgent-alerts
list, a recent-activity feed, and a lightweight "jump to a workspace" quick-link
row — *not* the big subsection cards that used to be the only way in. The old
`OperationsLanding.tsx` (card grid) was removed. Other sections keep their
config-driven `SectionLanding` card grids for now; the sidebar is the primary nav
regardless.

## 5. Routes preserved

No routes were removed. All of `/operations`, `/operations/customer-facing`,
`/operations/facility-facing`, `/operations/drivers`, `/operations/customer-orders`
(and every other section's subroutes) remain and are now reachable directly from
the sidebar.

## Related
- [[2026-07-22-sidebar-subnavigation-refactor]] (build report)
- `lib/dashboard/nav.ts`, `lib/dashboard/sections.ts`, `components/dashboard/shell/Sidebar.tsx`
