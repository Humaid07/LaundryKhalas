# Build Report — Sidebar Sub-Navigation Refactor

**Date:** 2026-07-22
**Author:** Engineering (Claude)
**Related:** [[dashboard-navigation]]

---

## 1. Build title
Convert the flat left sidebar into a **hierarchical nested navigation tree** and turn the Operations landing into a clean overview.

## 2. Objective
Stop forcing users to open a section landing and pick a subsection from big cards. Move every section's subsections into the **left sidebar** as nested, expand/collapse sub-tabs so any working page is one click away, with the parent staying highlighted while a child is active.

## 3. What navigation changed
- The sidebar is now a **two-level tree**: top-level section → nested subsection sub-tabs.
- Top-level items are **expandable/collapsible** (chevron), and the section containing the current route **auto-expands**.
- **Dual highlight**: the parent stays rose-highlighted on any child route (route-prefix match); the active child gets the filled treatment + rail (exact match).
- Clicking a section label still opens its landing/overview; clicking a child opens the subsection route directly.
- **Collapsed** desktop mode shows an icon-only rail; **mobile** drawer shows the full nested tree.
- The **Operations landing** is now a clean overview (KPIs, urgent alerts, recent activity, lightweight quick links) instead of four big navigation cards.

## 4. Which parent sections now have children
Operations, Sales, Partner Acquisition, SEO Agents, Marketing, Finance & Compliance, Dev & Automation, Reports, Settings. (Overview stays a single page.) See `dashboard-navigation.md` for the full child list per section.

## 5. Which routes were mapped
No new routes — every child links to an **existing** route under `app/(dashboard)/`. Children are derived from `sections.ts` as `${base}/${slug}`. Operations children map exactly to:
`/operations/customer-facing`, `/operations/facility-facing`, `/operations/drivers`, `/operations/customer-orders`. The `/operations` route itself is preserved as the overview.

## 6. Files changed
- **`apps/admin/lib/dashboard/nav.ts`** — rewritten: `NavItem` gains `children`, `defaultOpen`, `allowedRoles`; `NavChild` type added; children derived from `sections.ts` via `childrenOf()`.
- **`apps/admin/lib/dashboard/sections.ts`** — `Subsection` gains optional numeric `badge`; Operations subsections get child badges (7 / 3 / 12 / 82).
- **`apps/admin/components/dashboard/shell/Sidebar.tsx`** — rewritten to render the tree (`ParentRow` + `ChildRow`), with expand/collapse state, auto-expand, and dual highlight; collapsed/mobile preserved.
- **`apps/admin/components/dashboard/operations/OperationsOverview.tsx`** — NEW clean overview (KPI grid, urgent alerts, recent activity, quick links).
- **`apps/admin/app/(dashboard)/operations/page.tsx`** — renders `OperationsOverview`; title → "Operations Overview".
- **`apps/admin/components/dashboard/operations/OperationsLanding.tsx`** — REMOVED (the old big-card grid; replaced by the overview, no longer referenced).

## 7. UX reason
A real command center navigates from a persistent left rail, not from a landing page of cards. Nesting the subsections in the sidebar removes a redundant click, keeps context (parent + child both visible/highlighted), and frees the landing page to be an actual summary. Page-level tabs are reserved for *workflows within* a page (e.g. the Drivers page already has Driver Overview / Pickup Queue / Delivery Queue tabs).

## 8. Tests run
- `npx tsc --noEmit -p tsconfig.json` (admin).
- Live Playwright verification against the running dev server (:3005): screenshots of the Operations overview, a child route (`/operations/drivers`), an SEO child route (`/seo-agents/agent-fleet`), and collapsed mode.

## 9. Test results
- **tsc: 0 errors.**
- **Playwright (visual):**
  - `/operations` → Operations expanded with 4 children + badges (7/3/12/82), parent badge 6; overview shows KPIs + alerts + activity + quick links, no big nav cards. ✓
  - `/operations/drivers` → Operations parent highlighted (rose), Drivers child filled + rail, section auto-expanded; global filters bar present; page-level workflow tabs intact. ✓
  - `/seo-agents/agent-fleet` → SEO Agents expanded with all 10 children, Agent Fleet child active, Operations collapsed. ✓
  - Collapsed mode → icon-only rail, active section icon highlighted, no children/chevrons. ✓

## 10. Acceptance criteria — status
- Customer Facing / Facility Facing / Drivers / Customer Orders visible under Operations in the sidebar ✓
- Clicking each opens the correct route ✓
- Operations parent stays highlighted inside any Operations child route ✓
- Child route highlighted separately ✓
- Badges remain visible (parent aggregated + child specific) ✓
- Operations overview is cleaner; no duplicate nav cards required ✓
- Sidebar works on desktop, collapsed, and mobile drawer ✓
- Global filters still work ✓
- Existing routes/page components preserved (only the redundant `OperationsLanding` card component removed) ✓

## 11. Known limitations
- **Badges are illustrative** mock values (parent counts hardcoded in `nav.ts`, child counts in `sections.ts`). Wiring both levels to a single live-count aggregation is a follow-up.
- **Only the Operations landing** was redesigned into an overview; other sections keep their `SectionLanding` card grids (still reachable, but the sidebar is now the primary nav). Converting the rest to overviews is optional follow-up.
- The Operations pages still render the `OperationsSubNav` subsection pills at the top, which now partially duplicate the sidebar; these can be replaced by **workflow** top-tabs (the user's future "page-level tabs" — e.g. Customer Facing → WhatsApp Inbox / Tickets / Cancellations) in a later pass.
- Verified via tsc + live Playwright; `next build` is not run on Windows (known 500.html rename quirk).

## 12. Next recommended step
Add the per-page **workflow top-tabs** the user outlined (Customer Facing, Facility Facing, Customer Orders, Drivers) and replace the redundant subsection pill strip; then wire sidebar badges to live counts.
