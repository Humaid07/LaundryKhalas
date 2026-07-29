# Sidebar Polish — Fixed-Column Rows + Per-Section Accents

- **Date:** 2026-07-29
- **Scope:** `apps/admin` only (left sidebar + the central accent system it shares with the rest of the dashboard).
- **Branch:** `main` (no commits — working tree only).
- **Follows:** the ERP redesign ([[erp-dashboard-component-catalog]], `build-reports/2026-07-29-erp-dashboard-phase-*`).

## 1. Objective

Fix inconsistent sidebar rows (misaligned chevrons/badges, sections feeling too similar) and give each section a clear colour identity — without changing any routes or navigation behaviour.

## 2. What was built

### Fixed-column nav rows
Every top-level row is now a fixed 4-column grid — `grid-cols-[24px_1fr_auto_18px]`, `h-11`, `rounded-xl` — so icon, label, badge, and chevron always align:
- **Icon** column (24px, centred).
- **Label** column (`1fr`, `min-w-0` + `truncate` + `title` tooltip for long names like "Partner Acquisition", "Finance & Compliance").
- **Badge** column — always present (empty span when a section has no count), badges right-aligned and same width.
- **Chevron** column (18px) — always reserved; the chevron renders only for sections with children, but the space is held for every row so nothing shifts.
- Submenu toggle is a **transparent hit target** absolutely positioned over the chevron column (chevron no longer nests in the anchor and its x never depends on label length). Rotates only when expanded.

### Per-section colour identity (system-wide)
Moved the central accent system from **5 shared families** to **one unique hue per section** (owner decision), applied everywhere via `lib/dashboard/accents.ts` — so a section's colour is identical in the sidebar and on its pages:

| Overview | Operations | Orders | Sales | Partner | SEO | Marketing | Finance | Dev | Reports | Settings |
|---|---|---|---|---|---|---|---|---|---|---|
| slate | teal | sky | amber | violet | indigo | fuchsia | cyan | steel | plum | neutral |

`rose` stays the master brand (logo/primary actions) and maps to no section, so brand rose never competes with section identity. Green/lime avoided (reads as `success`).

- **Icon:** persistent subtle section tint at rest (`opacity-60`), brightens to full on hover/active — gives each row identity without a wall of colour.
- **Hover:** section-tinted background (`accent.hoverBg`, soft) + icon brighten, ~200ms, no layout shift.
- **Active:** stronger section tint (`accent.softBg`) + accent text + accent icon + left accent rail + badge in `accent.strongBg`.
- **Collapsed rail:** centred accent icon + `title` tooltip; no label/badge/chevron.
- **No horizontal scrollbar:** nav is `overflow-x-hidden`, labels truncate (verified `scrollWidth === clientWidth`).

## 3. Files created

- `docs/build-reports/2026-07-29-sidebar-polish-per-section-accents.md` (this report).

## 4. Files modified

- `apps/admin/app/globals.css` — added `--accent-sky/indigo/fuchsia/cyan/steel/plum` (light + dark); re-commented existing accents per-section.
- `apps/admin/tailwind.config.ts` — mapped the 6 new `accent.*` colours.
- `apps/admin/lib/dashboard/accents.ts` — expanded `AccentName` (11 hues + `rose` brand + `neutral`), per-section `MODULE_ACCENT`, added `hoverBg` + `strongBg` to every bundle.
- `apps/admin/components/dashboard/shell/Sidebar.tsx` — full row refactor (fixed grid, reserved badge/chevron columns, section-tinted hover/active, transparent toggle hit target, persistent icon tint, collapsed rail, `overflow-x-hidden`).
- `docs/architecture/erp-dashboard-component-catalog.md` — accent table (families → per-section) + new "Sidebar row structure" section.

## 5. Design-system note (reversal, documented)

The ERP redesign originally locked **accent families** (Phase 0). This task changes that to **per-section unique hues** at the owner's explicit request ("Unique hue per section, system-wide"), because families made grouped sidebar items look identical. Same architecture (`accents.ts` + tokens + kit props) — only the map/hue count changed. Because the whole app reads `accents.ts`, page headers, cards, sub-nav, and the ⌘K palette all updated to the per-section hues automatically and stay consistent with the sidebar.

## 6. What is mock-only / live / deferred

Presentation-layer only; no data, route, or navigation behaviour changed. No live effects.

## 7. Tests run / results

From `apps/admin`:

| Gate | Result |
|---|---|
| `npx tsc --noEmit` | ✅ 0 errors |
| `npm run lint` | ✅ 0 errors (1 pre-existing legacy `/admin` warning only) |
| `LK_DIST_DIR=.next-build npm run build` | ✅ **Exit 0** — compiled 36s, 97 pages prerendered |
| Playwright (light + dark + collapsed) | ✅ rows aligned; badges (6/5/3/4/3) + chevrons in fixed columns; per-section icon colours; section-tinted hover/active; **nav `scrollWidth === clientWidth` (no h-scroll)**; collapsed rail correct; **zero console errors** |

## 8. Acceptance criteria (from the request)

All met: equal row height ✅, icons/labels/badges/chevrons each at a constant x ✅, long labels truncate without pushing arrows ✅, arrow-less rows reserve arrow space ✅, badge-less rows reserve badge space ✅, unique section colour ✅, section-colour hover ✅ + stronger active ✅, smooth chevron rotation w/o layout shift ✅, no horizontal scrollbar ✅, collapsed works ✅, mobile drawer unaffected ✅, no route/navigation change ✅, submenus still open/close ✅, tsc ✅, lint ✅.

## 9. Known limitations / notes

- Dev-server restart is required after the `tailwind.config.ts` accent additions (documented gotcha — new `accent-*` utilities aren't hot-reloaded).
- The many cool/purple hues (sky/indigo/violet/plum/fuchsia/cyan/teal/steel) are necessarily adjacent given green + brand-rose are excluded; each is distinct enough at the small sizes used, but per-module uniqueness is inherently busier than the earlier family model (owner-chosen trade-off).

## 10. Security / privacy / cost

No change. No LLM usage.

## 11. Next recommended step

None required — task complete. Optional: if the palette ever feels too busy, the family model is one `MODULE_ACCENT` edit away. Recommend committing when ready (uncommitted on `main`).
