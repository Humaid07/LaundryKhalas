# ERP Dashboard Redesign — Phases 2–4: Component Kit, Module Rollout & Polish

- **Date:** 2026-07-29
- **Scope:** `apps/admin` only. No backend / agents / other apps / `supabase/`.
- **Branch:** `main` (owner decision; no commits — working tree only).
- **Follows:** [[2026-07-29-erp-dashboard-phase-0-audit-proposal]], [[2026-07-29-erp-dashboard-phase-1-tokens-shell]].
- **Status:** Complete — redesign finished. All gates green in light + dark.

> Executed Phases 2, 3, and 4 in one continuous pass (owner asked to run to completion). This report covers all three.

## 1. Objective

Build the reusable component layer (Phase 2), roll the new system across modules (Phase 3), and polish/QA/document (Phase 4) — completing the ERP-cockpit redesign on the Phase 1 foundation.

## 2. What was built

### Phase 2 — shared component kit
- **`HeroStat`** (`ui/StatCard`) — the headline-metric card: solid module-accent top-rule, accent icon chip, very large number, big sparkline or a `secondary` stat.
- **`accent` prop threaded through the kit** — `StatCard`, `StatGrid`, `HeroStat`, `Panel` (accent top-rule), `PanelHeader` (accent icon chip), `ChartCard` (rule + icon). Default `rose`.
- **`useAccentName()` / `useAccentClasses()`** (`lib/dashboard/use-accent.ts`) — client hook so a page resolves its module accent from the route and passes it down.
- **Component catalog doc** — `docs/architecture/erp-dashboard-component-catalog.md`: accent system, elevation scale, card-variant catalog, page grammar, filter/nav, do/don't. Reconciled with [[minimal-dashboard-design-system]].

### Phase 3 — module rollout
- **Unified the filter UX** — replaced the legacy inline 6-pill `FilterBar` with the consolidated `FilterMenu` (popover button + count badge) + `FilterChips` in all 5 Operations components (`CustomerFacing`, `Drivers`, `CustomerOrders`, `FacilityFacing`, `CustomerChargesPayments`). Now every page uses one filter mechanism.
- **Flagship Hero + accent** — Sales Overview subsection: `HeroStat` (Total Sales) in a 2×2 block inside a `KpiBand`, standard `StatCard`s around it, accent-ruled charts — all amber (Revenue family) via `useAccentName()`.
- **Finance analytics accent** — Finance financial-overview chart cards carry the amber accent.

### Phase 4 — polish, QA, docs
- Fixed the Hero card stretch (2×2 grid block instead of a full-height single cell).
- Removed the now-dead `components/dashboard/shell/FilterBar.tsx` and a stale comment reference.
- Full light/dark parity sweep across all 5 accent families; console-error check.
- This report + `00-Home.md` update + before/after summary.

## 3. Why

Phase 1 made the shell accent-aware globally but left the in-page kit rose-only and two filter mechanisms coexisting. Phases 2–4 give the reusable card set (so new modules are cheap), unify filters, demonstrate the Hero pattern on flagship pages, and remove dead code.

## 4. Files created

- `apps/admin/lib/dashboard/use-accent.ts`
- `docs/architecture/erp-dashboard-component-catalog.md`
- `docs/build-reports/2026-07-29-erp-dashboard-phase-2-4-kit-rollout-polish.md` (this report)

## 5. Files modified

- `ui/StatCard.tsx` — `accent` on `StatCard`/`StatGrid`; new `HeroStat`.
- `ui/primitives.tsx` — `accent` on `Panel`; `icon`+`accent` on `PanelHeader`.
- `ui/ChartCard.tsx` — `accent`+`icon` passthrough.
- `sales/Sales.tsx` — Hero + KpiBand + accent on the Overview subsection.
- `finance-compliance/FinanceCompliance.tsx` — accent on financial-overview charts.
- `operations/{CustomerFacing,Drivers,CustomerOrders,FacilityFacing,CustomerChargesPayments}.tsx` — `FilterBar` → `FilterMenu`+`FilterChips`.
- `dev-automation/DevAutomation.tsx` — comment fix.

## 6. Files deleted

- `apps/admin/components/dashboard/shell/FilterBar.tsx` (superseded by `FilterMenu`; no remaining importers).

## 7. API / DB / agent / integrations

No change (presentation layer only).

## 8. What is mock-only / live

All data mock (`mock-data.ts` / section `*-data.ts`); no live effects. Auth off locally.

## 9. What is intentionally deferred

- Deep reconciliation of the Finance **hybrid** (analytics vs. compliance in one router) — accented its charts, but its KPI strip stays minimal by design.
- Per-page Hero adoption on the remaining analytics subsections (Sales Markets/Channels/etc. keep standard grids) — the Hero pattern is demonstrated where a single headline metric exists.
- The main Overview page keeps its dense StatGrid (no Hero) — it is the deliberate information-rich exception per [[minimal-dashboard-design-system]].
- Minimal list pages stay chromatically quiet (no module accent on record cards) — a documented rule, not a gap.
- Command-palette role-filtering; URL-synced filters (pre-existing follow-ups).

## 10. Tests run / 11. Results

From `apps/admin`:

| Gate | Result |
|---|---|
| `npx tsc --noEmit` | ✅ 0 errors (Phase 2 caught + fixed a `Tone` vs `AccentName` mismatch in `HeroStat`) |
| `npm run lint` | ✅ 0 errors; only 1 pre-existing legacy warning (`app/admin/conversations`) remains |
| `LK_DIST_DIR=.next-build npm run build` | ✅ **Exit 0** — all routes prerendered |
| Visual (Playwright, light + dark) | ✅ Operations (teal), Sales Overview + Hero (amber), Finance (amber), Marketing (violet), Dev (slate); **zero console errors** |

## 12. Bugs / issues found

- **Hero stretch (fixed):** first Hero layout put the card in a single grid cell beside a 9-card column, stretching it to ~5 rows tall. Fixed with a `sm:col-span-2 sm:row-span-2` block.
- **`HeroStat` tone typing (fixed):** defaulting the sparkline tone to the module accent broke the `Tone` index type (accent names aren't tones); defaulted to `rose`.

## 13. Known limitations

- Finance remains a hybrid module (two visual languages in one router) — intentional; charts now accented, KPIs stay minimal.
- One legacy `/admin` lint warning remains (out of the redesign's scope).

## 14. Security / privacy

No change to data flow, PII masking, or the privacy firewall.

## 15. Cost / LLM usage

None.

## 16. Screens to demo

Overview (rose), Operations Customer Orders (teal + new Filters popover), **Sales Overview (amber, Hero KPI)**, Finance financial-overview (amber charts), Marketing (violet), Dev & Automation (slate) — light and dark.

## 17. Before vs after (for the weekly report / presentation)

| Aspect | Before | After |
|---|---|---|
| Module identity | Everything rose | 5 accent families (rose/teal/amber/violet/slate) across nav, header, cards, charts |
| Surfaces | Flat white on near-white; borders ~invisible in light | Layered canvas/surface/sunken + stronger borders; cards read elevated |
| KPIs | Uniform grid of identical cards | Hero KPI + KpiBand well + standard cards (clear hierarchy) |
| Filters | 6-pill wall on every page (two mechanisms) | One Filters popover + active chips (single mechanism everywhere) |
| Navigation | Sidebar-only, dead ⌘K hint | ⌘K command palette + accent-coded sidebar |
| Extensibility | Per-page styling | `accents.ts` + kit props + catalog doc → new module = config + composition |

## 18. Commands to run / verify

```bash
cd apps/admin && npm run dev          # http://localhost:3000 (auth off locally)
npx tsc --noEmit && npm run lint
# stop the dev server first (Windows), then:
LK_DIST_DIR=.next-build npm run build
```
Manual: open http://localhost:3000, switch modules (accent changes), toggle theme, press ⌘K, open Filters and set Region=UAE (chip + count appear), open Sales → Sales Overview (Hero KPI).

## 19. Next recommended step

Redesign complete. Optional follow-ups (not scheduled): role-filter the command palette, URL-sync filters, deeper Finance hybrid reconciliation, and (if desired later) per-module unique hues instead of families. Recommend committing the redesign when you're ready (currently uncommitted on `main`).
