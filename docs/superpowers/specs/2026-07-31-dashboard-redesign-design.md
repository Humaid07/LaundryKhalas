# Dashboard Redesign — Design Spec (Both Apps)

**Date:** 2026-07-31
**Branch:** `feat/dashboard-redesign` · **Baseline tag:** `pre-redesign-baseline` → `ca4517d`
**Scope apps:** `apps/admin` (Internal "Command Center", dev port **3000**) · `apps/facility-dashboard` (Partner Portal, dev port **3010**)
**Status:** Phase 0 complete (audit + reversibility + this spec). Awaiting owner review before Phase 1.

> Reversibility contract (owner's #1 rule):
> - **Preview redesign:** `git switch feat/dashboard-redesign` then run the apps.
> - **Roll back to current design:** `git switch main` (or hard-pin: `git checkout pre-redesign-baseline`).
> - All redesign work stays on the branch. Nothing merges to `main` without owner approval. Small, phase-scoped commits so any phase is individually revertible. **No runtime old/new toggle; no parallel old/new component code** (owner decision).

---

## 1. Objective

Professionally redesign and polish **both** dashboards into one coherent, premium, modern system — a real, production-quality implementation wired to the existing backend, **not** a static mock-up. Apply the reference video's *principles* (clear hierarchy, intentional colour, compact typography with tabular numbers, consistent spacing/grouping, simple data-viz, purposeful micro-interactions) to Laundry Khalas's real brand, IA, and operational data. Obey `CLAUDE.md` throughout (mock-first, log actions, privacy firewall, honest reporting, no live external calls without approval). **Presentation layer only** — preserve all business logic, APIs, auth, permissions, real-time updates, and audit logs.

## 2. Owner decisions (locked)

| Decision | Choice |
|---|---|
| Primary font | **Geist Sans** (body/UI) + **distinct display face** for titles/hero KPI |
| Personality | **Split**: internal ≈ calm/dense/keyboard-first (2–3); partner ≈ warmer/guided (4). One token system, two tunings. |
| Reversibility | Branch + tag only. No runtime toggle, no parallel old/new component code. |
| Legacy `/admin` island | **Token-fix the live handoff only** (`HumanInterventionQueue` + `OperationsOverview`); defer deeper `/admin` migration. |
| Unification | **Shared `packages/design/`** (tokens + Tailwind preset + fonts) via relative import (no npm workspace). Components stay per-app, reconciled to one canonical version. |
| Data scope | **Presentation-only.** Re-skin using existing data; never fabricate metrics; do not newly wire admin's mock pages to the backend (separate future work). |

## 3. Audit findings (file-grounded)

### 3.1 Strong foundation (extend, don't reinvent)
- **Identical stacks**: Next `^15.5.18`, Tailwind `^3.4.14`, React `^19.2.8`, TS `^5.6.3`, `recharts ^2.15.4`, `lucide-react`, `next-themes`, `@tanstack/react-query ^5.59` — same versions in both apps. No cross-app version blockers.
- **~99% identical tokens**: both `app/globals.css` files define the same CSS-var names *and RGB values* for surfaces (`--canvas/--surface/--surface-2/--surface-raised/--surface-sunken`), borders (`--border/--border-strong`), ink (`--ink/--ink-muted/--ink-faint`), rose (`--rose/--rose-strong/--rose-contrast`), semantic (`--success/--warning/--danger/--info`), chart palette (`--c-rose/plum/teal/amber/slate/sky`), and section accents — **both light (`:root`) and dark (`.dark`) fully defined**. Only real divergence: admin defines `--accent-orange` (Facilities); partner reuses `indigo` (`apps/facility-dashboard/lib/accents.ts:32`).
- **Same fonts today**: `Bricolage_Grotesque` (`--font-display`) / `Plus_Jakarta_Sans` (`--font-body`) / `Space_Grotesk` (`--font-numeric`) via `next/font/google` in each `app/layout.tsx`. `.tnum` tabular-figure utility applied consistently on metrics.
- **Same component lineage**: `ui/` primitives, `states`, `DataTable`, `Tabs`, `minimal/*` kit share shapes across apps (drifted by hand-edits). `lib/utils.ts` (`cn()`) is identical in both.
- **No monorepo tooling**: no root `package.json`/`workspaces`, no `packages/`, per-app lockfiles + `node_modules`.

### 3.2 Debt to fix (redesign targets)
**Both apps**
- No **type-scale tokens** — sizes re-picked per component as arbitrary values (`StatCard.tsx:54` `text-[1.6rem]`, `:117` `text-[2.4rem]`, `primitives.tsx` `text-[0.95rem]`, `PageHeader.tsx:76` `text-[1.7rem]`).
- **Competing KPI/card patterns** (≈3 per app): admin `StatGrid`/`StatCard` vs `MinimalKpiStrip` vs inline `Panel` KPIs (`OperationsOverview.tsx:63`); partner `MinimalKpiStrip` vs hand-rolled grids (`app/(app)/page.tsx:123`, `drivers/page.tsx:82`). Inconsistent chip opacity/ring (`/10` vs `/12`+ring).
- **Spinner-first loading**; `Skeleton` primitive exists but is barely used → layout jump.
- Raw `<img>` PNG brand mark, no SVG/dark variant (`shell/Brand.tsx`).
- Border-heavy elevation (global `*{border-color}` + per-component `border`), hierarchy carried by lines not space/shadow.

**Internal (`apps/admin`)**
- **Legacy `/admin` island** (`components/layout/AdminSidebar.tsx:29-62` `bg-gray-950`/`text-gray-*`; `components/ui/*` on stale non-theme `brand/neutral/*-soft` hex) — orphaned from `nav.ts` but **deep-linked from a live component**: `HumanInterventionQueue.tsx:203` → `/admin/conversations/...`.
- **Off-token components in the new app**: `operations/HumanInterventionQueue.tsx:14,102-221` (all `slate-*`/`bg-white`/`bg-slate-900`, broken in dark mode); `operations/OperationsOverview.tsx:52-57` (shadow `toneText` with raw `emerald/red/amber/purple/sky`).
- **No `ErrorState`** in canonical `dashboard/ui/states.tsx`; **no shared control-chrome class** (icon-button recipe copy-pasted across `Topbar.tsx:31,47,58`, `ThemeToggle.tsx:21`, `UserMenu.tsx:49`).
- Overcrowded overview: `OperationsOverview.tsx:63` 6-col KPI grid, no focal metric. Badge overload from hardcoded `nav.ts` counts. Dead **Bell** (`Topbar.tsx:55-62`, no handler).

**Partner (`apps/facility-dashboard`)**
- **Three header components** for one job: `shared/MobilePageHeader` (used everywhere), `minimal/MinimalPageHeader` (**dead — imported by zero pages**), `settings/SettingsHeader`.
- **Divergent facility-status vocabulary**: `components/facilities/FacilityManager.tsx:22-28` hardcodes `open/busy/paused/closed`; shared `lib/status.ts:97-115` knows `accepting/open/paused/closed` with **no "busy"**.
- **Three KPI implementations**; two/three import paths for the same `states` (`ui/states.tsx` ↔ `shared/states.tsx` ↔ `minimal/index.ts`).
- Facilities accent missing (`indigo` instead of admin `orange`). Dead legacy Tailwind aliases (`tailwind.config.ts:49-55`).
- **Good news**: partner pages are largely backend-wired already (orders/finance/drivers/issues/facilities); weak spots are thin wrappers (`facilities/page.tsx` 19-line wrapper → `FacilityManager`; `settings` index) + spinner loading, not fake data.

### 3.3 Honest scope note — "real data"
Partner-portal pages are mostly backend-wired. **Most `apps/admin` `(dashboard)` pages render baked-in static/mock data** (thin server wrappers → section components with inline mock arrays, e.g. `OperationsOverview.tsx:19-50`). Per owner decision, the redesign is **presentation-only**: re-skin using existing data, keep mock pages honestly labelled (per the "no mock/demo words in UI" rule use *Staged/Standby/Coming soon/Operational*, never "mock"), **never fabricate metrics**, and do **not** newly wire those pages to the backend in this initiative.

## 4. Design system (Phase 1 foundation)

### 4.1 Shared source of truth — `packages/design/`
New repo-level folder (no npm workspace needed):
- `packages/design/tokens.css` — canonical CSS-var token block (superset incl. `--accent-orange`) + the `.lk-*` utility/keyframe layer. Each app's `app/globals.css` `@import`s it, then may add app-only overrides.
- `packages/design/tailwind-preset.ts` — the shared `theme.extend` fragment (colour `token()` map, `fontFamily`, `borderRadius`, `boxShadow`, `fontSize` incl. new type-scale, `letterSpacing`, timing). Each app's `tailwind.config.ts` sets `presets: [require('../../packages/design/tailwind-preset')]` and keeps only its `content` globs. Each app's `content` must also include the package path.
- `packages/design/fonts.ts` — `next/font` setup exporting the font `variable` class string; both `layout.tsx` files consume it.
- **Components stay per-app** but are reconciled to one canonical implementation and kept structurally identical (drift is the current pain; this removes it without over-abstracting). A future `packages/ui` workspace is possible but out of scope.

### 4.2 Fonts
- **Body/UI:** Geist Sans → `--font-body` (replaces Plus Jakarta Sans).
- **Display (titles + hero KPI):** keep **Bricolage Grotesque** → `--font-display` (distinct editorial contrast, minimal churn). *Alternative to preview: a tighter grotesk; owner to confirm from samples.*
- **Numeric/mono (IDs, money, timestamps):** **Geist Mono** → `--font-numeric`, `.tnum` tabular retained.
- All via `next/font` (no FOUT/layout shift), wired to existing `--font-*` vars so components pick them up centrally.

### 4.3 Type scale (new tokens)
Named sizes added to the preset (hierarchy from weight+spacing, not big headings): `page-title` 24–28 · `section` 18–20 · `card-title` 14–16 · `body` 14 · `table` 13–14 · `secondary` 12–13 · `label` 11–12; plus `metric-lg`/`metric-sm` for KPI values. Replace arbitrary `text-[…]` usages.

### 4.4 Spacing / radius / depth / colour
- 4px spacing scale (4/8/12/16/20/24/32); remove arbitrary values.
- Radius restrained: controls 6–8 · cards/inputs 10–12 · modal/drawer 14–16 · pills only where semantic.
- Elevation: prefer **surface contrast + subtle border**; `shadow-pop` only for floating (menus/popovers/modals/drawers). Cards stay distinct from canvas.
- Rose = **signal, not fill** (primary action, selected nav, focus, key highlights, small charts). Status colours never colour-only (pair with dot/icon/label). Standardise one badge family + one **control-chrome** class (shared icon-button/border/hover/focus recipe) + add canonical **`ErrorState`** + skeleton-first loading.

## 5. Two personalities, one system
- **Internal = ops command center:** denser but organized, fast scanning, prioritized alerts, calm base so critical items stand out (sparing red/amber/rose), keyboard-friendly. Motion 120–180ms.
- **Partner = simpler/friendlier/guided:** more whitespace, today's-work focus, clear next actions, helper text for unfamiliar operations, slightly more motion (still <250ms). **Never** expose internal-only fields/rates/quality scores/admin data; preserve all backend permission restrictions.

## 6. Phased plan (each = own commit + owner approval gate)

Every phase: work on `feat/dashboard-redesign`; run `lint` + `tsc --noEmit` + `build` for **both** apps; verify **light and dark**; capture before/after screenshots; put preview+revert commands atop the phase report.

- **Phase 1 — Foundation:** `packages/design/` (tokens+preset+fonts); Geist wiring; type-scale tokens; reconcile Button/Badge/Input/Tooltip; skeleton-first loading + add `ErrorState`; shared control-chrome class. *No layout moves; type + controls sharpen globally.*
- **Phase 2 — App shell (both):** sidebar grouping/active-state simplification (not colour-only), collapse+memory, mobile drawer/bottom-nav parity, topbar (retire or wire the dead Bell), breadcrumbs, single SVG Brand, long-label scroll on hover+focus (reduced-motion safe).
- **Phase 3 — Internal pages** (reviewable batches): overview (focal HeroStat, de-crowd 6-col grid) → operations incl. **token-fixing `HumanInterventionQueue` + `OperationsOverview` (fixes dark mode + gray-console handoff)** → facilities → remaining real pages.
- **Phase 4 — Partner pages:** overview → facility → orders → finance → settings; consolidate 3 headers → 1, unify facility-status vocabulary (adopt shared `lib/status.ts`, resolve "busy"), one KPI primitive, add Facilities accent.
- **Phase 5 — Interactions:** popover/drawer/modal/toast conventions, contextual bulk-action bar (hidden until selection), chart hover/emphasis, **safe** optimistic UI only (status/mark-read/assign/toggle — never financial/destructive), micro-interactions on transform/opacity, `prefers-reduced-motion` honoured.
- **Phase 6 — Validation:** responsive 1920→320, a11y (visible focus, keyboard, AA contrast, dialog focus-trap/restore/Esc, `aria-live`, ~44px targets), performance (no needless rerenders, lazy heavy charts, no layout shift, no big new animation libs), and full lint+tsc+build+tests for both apps.

## 7. Preserve / do-not-break checklist
Backend APIs · DB ops · auth · role/permission checks · real-time updates/subscriptions · forms/tables/filters/filter-counts · WhatsApp agent integration · facilities management · conversation handling · order/pricing/customer/driver/payment management · partner ownership restrictions · audit logs. Keep the **compact Filter + active-filter chips** direction for conversations (do **not** restore permanent filter pills). Never expose internal-only data in the Partner Portal.

## 8. Testing & acceptance
Per-phase: typecheck, ESLint, frontend tests, affected backend tests, production build for both apps; manual pass of the flows in `CLAUDE.md §22`; light+dark; responsive; before/after screenshots when tooling available. **Never claim pass without running it.** Done when: both apps share one design system; typography/ hierarchy/cards/tables/charts/states/feedback all improved and consistent; safe interactions feel immediate; desktop/tablet/mobile all work; a11y improved; **backend + partner privacy intact; both production builds pass; no major regression; and the old design is one command away.**

## 9. Risks / limitations
- Admin mock pages remain mock (presentation-only) — honestly labelled, not "live".
- No npm workspace: shared `packages/design/` consumed via relative path + preset; each app's Tailwind `content` must include the package path for JIT.
- Reconciling drifted components (`ui/states`, `ui/primitives`, `ui/Tabs`, `minimal/*`) means choosing/merging one canonical version per component.
- Legacy `/admin` deeper pages remain off-brand this round (only the live handoff is token-fixed).

## 10. Next step
On owner approval of this spec → invoke **writing-plans** to produce the detailed **Phase 1 (Foundation)** implementation plan. Each subsequent phase gets its own plan → implement → review cycle.
