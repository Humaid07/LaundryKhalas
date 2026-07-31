# Build Report — Dashboard Redesign: Foundation + Full Token-Migration

**Date:** 2026-07-31
**Branch:** `feat/dashboard-redesign` (pushed to origin; PR-ready) · **Baseline tag:** `pre-redesign-baseline` → `ca4517d`
**Apps:** `apps/admin` (Internal Command Center, :3000) · `apps/facility-dashboard` (Partner Portal, :3010)

## 1. Objective
Professionally redesign both dashboards into one coherent, premium, dark-mode-correct system wired to the real backend — reversibly (old design one command away), presentation-only, no fabricated data.

## 2. Reversibility (owner's #1 rule)
- **Preview:** `git switch feat/dashboard-redesign` → run apps.
- **Roll back:** `git switch main` (or `git checkout pre-redesign-baseline`).
- All work on the branch; `main` untouched. No runtime toggle, no parallel old/new component code. Small phase-scoped commits.

## 3. What was built (by phase)
**Phase 0 — Audit + spec** (`5cb86ac`): 3 parallel audits (admin/facility/shared-system), design spec `docs/superpowers/specs/2026-07-31-dashboard-redesign-design.md`, Phase-1 plan.

**Phase 1 — Shared design system (COMPLETE)** (`eee0c4c`, `996bd8d`, `f1f1a7a`):
- New `packages/design/` = single source of truth: dependency-free Tailwind **preset** + `tokens.ts` injecting `:root`/`.dark` CSS-var tokens via `addBase`. Both apps' `globals.css` dropped their duplicated token blocks; both `tailwind.config.ts` consume the preset. Preset now has **zero hardcoded hex**.
- Fonts → **Geist Sans** (body) + **Geist Mono** (numeric), keeping **Bricolage Grotesque** (display).
- Named **type scale** tokens (page-title/section/card-title/metric-lg/metric/metric-sm), adopted across header/metric components.
- Shared **`.lk-control`** chrome class for icon buttons; dependency-free **Tooltip** primitive; **ErrorState** added to admin (parity with facility).

**Phase 2 — Shell honesty** (`803617f`): retired the non-functional admin notification bell + its fabricated "unread" dot; removed hardcoded fabricated sidebar badge counts (§7 no invented data).

**Phase 3 — Full token-migration (COMPLETE)** (`6303de7`, `cb9b820`, `57cc6d9`, `e837d09`, `01a6d43`):
- `OperationsOverview` + `HumanInterventionQueue` (live components) → token colours; **distinct priority ramp** (CRITICAL=danger/HIGH=warning/MEDIUM=info/NORMAL=neutral).
- Legacy `/admin` console (sidebar/topbar/ui-kit/pages) + supporting components (conversations/approvals/logs/orders) → tokens. ~187 class swaps total.
- Result: every admin surface + facility renders correctly in **dark mode**; no hardcoded palette/hex in app source (only stale `.open-next/` build artifacts).
- De-crowded the Operations KPI wall (6-across → 3-up) + type scale.

**Phase 4 — Partner consistency** (`4257f6e`, this report): unified facility operating-status vocabulary — `lib/status.ts` canonical (open/accepting=success, **busy=warning**, paused=neutral, closed=danger) + `OPERATING_STATUSES`; `FacilityManager` consumes shared `operatingTone`/`operatingLabel`/`toneChip` (dropped its private map). Removed dead `MinimalPageHeader`.

**Phase 6 — Validation:** lint + typecheck sweep on both apps (see §6).

## 4. Files
- **Created:** `packages/design/{tokens.ts,tailwind-preset.ts,README.md,verify-preset.mjs}`; `Tooltip.tsx` (both apps); this report + spec + plan docs.
- **Modified:** both `tailwind.config.ts` + `globals.css` + `layout.tsx`; ~30 admin components (type scale + token migration + `.lk-control`); facility `layout.tsx`, `lib/status.ts`, `FacilityManager.tsx`, `FacilityHeader.tsx`, header/metric/drivers components.
- **Deleted:** `apps/facility-dashboard/components/minimal/MinimalPageHeader.tsx` (dead).

## 5. Mock / live / deferred
- **Presentation-only.** Admin `(dashboard)` pages remain their existing static/mock data (honestly, not wired anew); partner pages are backend-wired. No fabricated metrics.
- **Deferred:** subjective shell polish (sidebar active-state density), unifying partner KPI cards to `MinimalKpiStrip`, Phase 5 interaction patterns (bulk-action bar, optimistic UI beyond current), deeper legacy `/admin` page redesign.

## 6. Tests / verification
- **Per-commit:** `tsc --noEmit` exit 0 on every change (both apps); dev servers compiled + served 200; grep-clean for palette/legacy-token classes.
- **Playwright visual pass (light + dark):** verified internal Overview, Operations (de-crowd + dark tokens), partner shell + real facility name, and the status-vocabulary fix (Busy → amber chip in header/card/dropdown/overview). Backend `:8100` started to unblock the auth gate.
- **Phase 6 sweep:** lint + typecheck both apps — see completion summary.
- **Note:** `next build` is unusable on Windows here (pre-existing `/_document` prerender quirk); verification is tsc + dev + Playwright per repo practice.

## 7. Known limitations / caveats
- Both apps gate all rendering behind the backend auth (`AuthProvider` → `:8100`); with `:8100` down they sit on "Loading…". Backend must run to view.
- "Orders by city" (admin overview) looks sparse — thin-but-real seeded data (one city), not a render bug.
- Subjective visual phases (sidebar density, etc.) are best iterated in a focused session with a live visual loop.

## 8. Security / privacy
No business logic, auth, permissions, data, or partner-privacy boundaries changed — presentation layer only. Partner Portal still exposes no internal-only fields/rates.

## 9. How to verify manually
1. Start backend: `cd apps/whatsapp-agent && ./.venv/Scripts/python.exe -m uvicorn main:app --port 8100`.
2. `cd apps/admin && npm run dev` (:3000) and `cd apps/facility-dashboard && npm run dev` (:3010).
3. Open both, toggle light/dark — confirm consistent tokens, Geist type, and (admin) the legacy `/admin/*` pages now match the brand in dark mode.

## 10. Next recommended step
Open the PR from `feat/dashboard-redesign`. Then, in a fresh focused session, iterate the subjective visual polish (sidebar active-state, partner KPI unification, Phase 5 interactions) with a live Playwright loop.
