# Facility Dashboard — ERP Design Parity (tokens + per-section accents + nav)

- **Date:** 2026-07-29
- **Scope:** `apps/facility-dashboard` only (mobile-first partner portal, :3010). No backend / other apps / `supabase/`.
- **Branch:** `main` (no commits — working tree only).
- **Follows / mirrors:** the admin ERP redesign ([[erp-dashboard-component-catalog]], `build-reports/2026-07-29-erp-dashboard-*`, `2026-07-29-sidebar-polish-*`).

## 1. Objective

Replicate the admin dashboard's ERP design principles in the facility (partner) app: layered surfaces + stronger borders, and one distinct **section accent** applied consistently across the desktop sidebar, the mobile bottom nav, and page headers — so each section has its own identity. Adapted to a mobile-first, privacy-firewalled partner portal.

## 2. What was built

### Extended tokens (ported from admin)
`app/globals.css` + `tailwind.config.ts`: deeper warm light canvas (`248 244 246`), new `--surface-sunken`, stronger light+dark borders, and the section-accent token set (`--accent-teal/amber/violet/slate/sky/indigo/fuchsia/cyan/steel/plum`, light + dark). Mapped `surface.sunken` + `accent.*` in Tailwind. The facility app previously carried the admin's *pre-redesign* tokens, so this brings it to parity.

### Facility section-accent map
New `lib/accents.ts` (same architecture as admin `lib/dashboard/accents.ts`), keyed to the facility's six sections — Home handled via the empty-segment case:

| Home | Orders | Drivers | Finance | Issues | Settings |
|---|---|---|---|---|---|
| teal | sky | violet | cyan | amber | neutral (gray) |

`rose` stays the master brand (logo, notification badge). Green/lime avoided (reads as status). `accentForPath`/`accentForHref`/`accentClasses*` + `ACCENT_CLASSES` bundles (`text/chip/rail/softBg/hoverBg/strongBg/ring/dot`), all literal for the JIT.

### Navigation — per-section identity
- **Desktop sidebar** (`FacilityDesktopShell`): every row is a fixed grid (`icon · label · badge`), with a **persistent section-tinted icon** (opacity 60 → 100 on hover/active), section-tinted hover, and an accent **active** state (soft accent bg + accent text + left accent rail + accent badge). `overflow-x-hidden`.
- **Mobile bottom nav** (`FacilityBottomNav`): the active tab uses its section accent (icon + label) plus a small accent **top indicator** bar, instead of always-rose. Unread count on Orders stays rose (brand alert).

### Page headers / cards
- `MobilePageHeader` — now accent-aware: eyebrow tinted with the section accent (resolved from the route) + optional accent icon chip.
- `shared/SectionCard` — header icon uses the section accent (route-resolved, or an explicit `accent` prop) instead of hardcoded rose.

## 3. Files created / modified

- **Created:** `apps/facility-dashboard/lib/accents.ts`.
- **Modified:** `app/globals.css`, `tailwind.config.ts`, `components/layout/FacilityDesktopShell.tsx`, `components/layout/FacilityBottomNav.tsx`, `components/shared/MobilePageHeader.tsx`, `components/shared/SectionCard.tsx`.

## 4. What is mock-only / live / deferred

- Presentation-layer only — no routes, data, API, or navigation behaviour changed. Auth off locally (`/api/auth/config → auth_required:false`), so the app renders without a partner login.
- **Privacy firewall respected:** purely visual; no change to what data is shown. The facility PII whitelist (area/city only, first-name label, masked phones, `pending_rate` payout) is unaffected. See [[facility-privacy-firewall]].
- **Deferred (not needed here):** Hero KPI rollout and deep per-page restyle — the facility app is minimal-first by design ([[minimal-dashboard-design-system]]); the nav + header + card accents carry the identity. Consolidating the near-duplicate primitives (`ui/states` vs `shared/states`, `MinimalPageHeader` vs `MobilePageHeader`) is a separate cleanup, out of scope.

## 5. Tests run / results

From `apps/facility-dashboard`:

| Gate | Result |
|---|---|
| `npx tsc --noEmit` | ✅ 0 errors |
| `npm run lint` | ✅ 0 errors (1 pre-existing warning in `orders/page.tsx`, untouched) |
| `LK_DIST_DIR=.next-build npm run build` | ✅ **Exit 0** — compiled 38.5s, 20 pages |
| Playwright (desktop sidebar + mobile bottom nav, light + dark) | ✅ per-section icon colours; Drivers active = violet (bg + text + icon + rail); Orders active tab = sky + top indicator; layered surfaces; **zero console errors** |

## 6. Security / privacy / cost

No change to data flow, the PII firewall, or auth. No LLM usage.

## 7. Known limitations

- Dev-server restart required after the `tailwind.config.ts` accent additions (new `accent-*` utilities aren't hot-reloaded).
- Section accents match the admin hues so the two apps read as one product; the facility map is intentionally smaller (6 sections).

## 8. Next recommended step

Task complete. Optional later: consolidate the duplicate facility primitives onto the `minimal/` kit; add accent-aware `Panel`/`ChartCard` (as in admin Phase 2) if the home overview grows more chart-heavy. Recommend committing when ready (uncommitted on `main`).
