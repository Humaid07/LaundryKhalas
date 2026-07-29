# ERP Dashboard Redesign — Phase 1: Design Tokens + Shell

- **Date:** 2026-07-29
- **Scope:** `apps/admin` only. No backend / agents / other apps / `supabase/`.
- **Branch:** `main` (owner decision; no commits made — working tree only).
- **Follows:** [[2026-07-29-erp-dashboard-phase-0-audit-proposal]] (decisions locked there).
- **Status:** Complete — verified in light + dark, gates green. Awaiting review before Phase 2.

## 1. Task objective

Implement the extended design tokens and restyle the shell so the dashboard reads as a modern ERP cockpit: layered surfaces + stronger borders, per-module accent identity (families), a consistent page grammar (breadcrumb → header → KPI band → content), and a decluttered filter/nav layer (consolidated Filters popover + ⌘K command palette). Rose stays the master brand.

## 2. What was built

1. **Extended token layer** — warmer/deeper light canvas, a new `surface-sunken` elevation layer, stronger light+dark borders, and 4 module-accent tokens (teal/amber/violet/slate) with light **and** dark values.
2. **Module-accent single source of truth** — `lib/dashboard/accents.ts`: `MODULE_ACCENT` family map + literal `ACCENT_CLASSES` bundles + `accentForPath`/`accentClasses*` helpers.
3. **Shell restyle** — Sidebar active states, SectionSubNav active pill, and SectionCard now use the current module's accent instead of always-rose.
4. **Page grammar** — `ResponsivePageHeader` is now a client component that auto-derives the module accent + icon chip from the pathname, tints the eyebrow, and supports an optional breadcrumb. New `KpiBand` layout primitive for the headline-metrics slot.
5. **Filter declutter** — the always-visible 6-pill wall is replaced (in page headers) by one **Filters** popover button with an active-count badge + an always-visible active-chip row (`FilterMenu` / `FilterChips`). `FiltersProvider` contract + `FilterSelect` a11y untouched.
6. **⌘K command palette** — `CommandPalette` wired into the Topbar (⌘K/Ctrl+K + click the search box); jumps to any section/subsection, accent-coded, keyboard-driven.

## 3. Why

Phase 0 audit found near-invisible light-mode surfaces/borders, rose-only styling (no module identity), a heavy 6-dropdown filter wall, and a dead ⌘K affordance. This phase fixes the foundation so Phases 2–3 can compose modules on top of it cheaply.

## 4. Files created

- `apps/admin/lib/dashboard/accents.ts` — module-accent system (families, class bundles, resolvers).
- `apps/admin/components/dashboard/shell/FilterMenu.tsx` — consolidated Filters popover + `FilterChips`.
- `apps/admin/components/dashboard/shell/CommandPalette.tsx` — ⌘K palette.
- `docs/build-reports/2026-07-29-erp-dashboard-phase-1-tokens-shell.md` — this report.

## 5. Files modified

- `apps/admin/app/globals.css` — light/dark surface + border tokens; `--surface-sunken`; 4 `--accent-*` tokens (light+dark).
- `apps/admin/tailwind.config.ts` — `surface.sunken` + `accent.{teal,amber,violet,slate}` colour mappings.
- `apps/admin/components/dashboard/shell/PageHeader.tsx` — client component; accent eyebrow + icon chip; optional breadcrumb; renders `FilterMenu` + `FilterChips` instead of the inline 6-pill bar.
- `apps/admin/components/dashboard/shell/Sidebar.tsx` — module-accent active/filled states (was rose).
- `apps/admin/components/dashboard/shell/Topbar.tsx` — search box opens the palette; global ⌘K listener; mounts `CommandPalette`.
- `apps/admin/components/dashboard/section/SectionSubNav.tsx` — accent active pill.
- `apps/admin/components/dashboard/section/SectionCard.tsx` — accent icon chip + top-rule + hover border + CTA.
- `apps/admin/components/dashboard/section/SectionLanding.tsx` — passes a breadcrumb.
- `apps/admin/components/dashboard/ui/primitives.tsx` — new `KpiBand` primitive.
- `apps/admin/app/(dashboard)/overview/page.tsx` — adopts `KpiBand` (verification target).
- `apps/admin/components/dashboard/operations/pricing/PricingManagement.tsx` — escaped 2 apostrophes (pre-existing lint error, blocked the production build).
- `apps/admin/components/dashboard/settings/UserManagement.tsx` — escaped 1 apostrophe (same reason).

## 6. API endpoints added/changed

None. Presentation-layer only.

## 7. Database tables/models added/changed

None.

## 8. UI pages/components added/changed

- New shell components: `FilterMenu`, `FilterChips`, `CommandPalette`. New primitive: `KpiBand`.
- Restyled (behaviour unchanged): Sidebar, Topbar, PageHeader, SectionSubNav, SectionCard, SectionLanding, Overview.
- All existing routes, links, and the `FiltersProvider` / `nav.ts` / `sections.ts` contracts preserved.

## 9. Agent behaviour / 10. Integrations

No change.

## 11. What is mock-only

Everything — all data still from `lib/dashboard/mock-data.ts` / `sections.ts`. No new operational data invented. No live WhatsApp/Stripe/LLM effects. Auth is off locally (`/api/auth/config → auth_required:false`), so the dashboard renders without login.

## 12. What is live

Nothing new is live.

## 13. What is intentionally deferred

- **Hero KPI card variant** + full card-variant catalog → Phase 2.
- **Rolling the grammar/accents across all modules** → Phase 3 (this phase applied the shell-level changes globally + verified Overview and Sales; the inline `FilterBar` still used *inside* several Operations components — `CustomerFacing`, `Drivers`, `CustomerOrders`, `FacilityFacing`, `CustomerChargesPayments` — is untouched and still shows the 6-pill bar per-tab; unified in Phase 3).
- Role-gating the command palette results (shows all destinations for now; routes remain backend-guarded).
- URL-syncing filters (already a documented pre-existing next step).

## 14. Tests / 15. Test results

Run from `apps/admin`:

| Gate | Command | Result |
|---|---|---|
| Typecheck | `npx tsc --noEmit` | ✅ Pass (0 errors) |
| Lint | `npm run lint` | ✅ No errors in changed files. (Fixed the 3 pre-existing `react/no-unescaped-entities` errors; one pre-existing `react-hooks/exhaustive-deps` **warning** remains in the legacy `app/admin/conversations` page — out of scope, non-blocking.) |
| Production build | `LK_DIST_DIR=.next-build npm run build` | ✅ **Exit 0** — compiled in ~24s, all routes prerendered. (Was red before the apostrophe fixes.) |
| Visual (Playwright) | Overview + Sales landing + Sales subsection, **light & dark**; ⌘K palette; Filters popover | ✅ Renders correctly in both themes; **zero console errors/warnings** |

## 16. Bugs / issues found

- **Pre-existing production-build blocker (now fixed):** 3 `react/no-unescaped-entities` lint errors in `PricingManagement.tsx` (2) and `UserManagement.tsx` (1) failed `next build`. These pre-dated Phase 1; escaping the apostrophes (`&apos;`) unblocked the build.
- **Tailwind config reload gotcha (dev workflow, not a code bug):** new `accent-*` colours require a dev-server restart to compile — a running dev server won't hot-reload `tailwind.config.ts`. First verification pass showed un-tinted accents until restart. Documented so future token work restarts the server.

## 17. Known limitations

- Two filter UIs coexist during the migration: the new header popover (landing/subsection pages via `SectionLanding`/`SubsectionShell`) and the legacy inline `FilterBar` inside the Operations components listed in §13. Intentional; unified in Phase 3.
- Command palette is not yet role-filtered.

## 18. Security / privacy notes

No change to data flow, PII masking, or the privacy firewall — styling/layout only.

## 19. Cost / LLM usage

None — no LLM calls.

## 20. Screens to demo

Overview (rose/Command), Sales landing + Sales Overview subsection (amber/Revenue), Operations (teal/Fulfilment), the ⌘K palette, and the Filters popover — each in light and dark.

## 21. Commands to run

```bash
# backend (from apps/whatsapp-agent, venv)
.venv/Scripts/python.exe -m uvicorn main:app --host 127.0.0.1 --port 8100
# admin dashboard (from apps/admin)
npm run dev            # http://localhost:3000  (auth off locally)
# gates
npx tsc --noEmit && npm run lint
LK_DIST_DIR=.next-build npm run build   # stop the dev server first (Windows)
```

## 22. How to verify manually

Open http://localhost:3000 → Overview. Switch modules in the sidebar and confirm the accent changes (rose → teal → amber → violet → slate). Toggle the theme (top bar) and confirm both themes. Press ⌘K and jump to a subsection. Click **Filters**, set Region = UAE, confirm the active chip appears under the header and the button shows a count badge.

## 23. Next recommended step

**Phase 2 — Shared component kit:** add the Hero KPI variant + `accent` prop on `Panel`, refine `StatCard`/`ChartCard`/`DataTable`/`StatusBadge`, thread module-accent plumbing through the kit, and write the component-catalog doc (reconciled with [[minimal-dashboard-design-system]]). Stop for review after.
