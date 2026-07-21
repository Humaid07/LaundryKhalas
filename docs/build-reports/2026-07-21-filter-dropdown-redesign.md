# Build Report — Filter dropdown redesign (custom FilterSelect)

**Date:** 2026-07-21
**App:** `apps/admin` · global FilterBar + LocalFilterBar (all dashboard sections)
**Status:** ✅ Typechecked (0 errors) · compiled successfully · browser-verified (light/dark/mobile, functional + visual). UI-only, mock-only. See §9 for an honest note on the production-build step.

---

## 1. Objective
The global filter bar used native `<select>` elements that rendered as generic gray
browser dropdowns — inconsistent with the premium pink/white LaundryKhalas design
system. Replace them with one reusable, custom, accessible dropdown that looks modern,
rounded and on-brand, **without changing any filter logic**.

## 2. What changed
- Built a new reusable **`FilterSelect`** component — a dependency-free custom listbox
  (no native `<select>`, no UI-library dependency) with premium rounded-pill triggers,
  a rounded-2xl popover menu, rose accent for the active/selected state, smooth
  transitions, and full keyboard + screen-reader accessibility.
- Swapped it into **both** filter surfaces so there is a single dropdown component
  everywhere: the **global `FilterBar`** (Date/Market/Region/City/Channel/Service) and
  the **`LocalFilterBar`** (Partner Acquisition, Dev & Automation, etc.).
- Removed the two duplicated inline native-`<select>` implementations.
- Polished the "Clear all" buttons in both bars to match the new pill language
  (same `h-9`, `rounded-full`, rose focus ring).
- Added a small `lk-menu-in` keyframe (soft scale + fade from the top) in `globals.css`.

No filter engine, provider, mock data or API changed. The component is a drop-in visual
replacement — same `label/value/options/onChange` prop shape the call sites already used.

## 3. Files created
- `apps/admin/components/dashboard/ui/FilterSelect.tsx`
- `docs/build-reports/2026-07-21-filter-dropdown-redesign.md` (this file)

## 4. Files modified
- `apps/admin/components/dashboard/shell/FilterBar.tsx` — import + use `FilterSelect`;
  deleted the inline native `<select>`; pill-styled "Clear all".
- `apps/admin/components/dashboard/ui/LocalFilters.tsx` — same swap; deleted its inline
  `Select`; pill-styled "Clear all".
- `apps/admin/app/globals.css` — added `@keyframes lk-menu-in` + `.lk-menu-in`.
- `docs/architecture/internal-dashboard-ui.md`, `docs/checklists/internal-dashboard-ui-test-script.md`,
  `docs/00-Home.md` — documented the new dropdown.

## 5. How the new dropdown works
**Trigger** — a rounded-full pill button (`role="combobox"`, `aria-haspopup="listbox"`,
`aria-expanded`, `aria-label`). Default: soft border, surface bg, hover lifts to
`surface-2` + `border-strong`. **Active** (a value selected): rose border + rose tint +
rose text. **Open**: rose-tinted border + card shadow. A chevron rotates 180° while open.
Optional `icon` (leading) and `clearable` (inline × button) props.

**Menu** — an absolutely-positioned `role="listbox"` on `bg-surface-raised`, `rounded-2xl`,
`border`, `shadow-pop`, `max-h-72` scroll, entering with the `lk-menu-in` animation. It
**auto-flips to right-align** when the trigger sits past ~60% of the viewport width, so it
never runs off-screen. Width is capped at `min(16rem, calc(100vw − 2rem))` so it can never
cause horizontal page overflow.

**Options** — `role="option"` rows, `rounded-lg`. A leading **"All {label}"** row maps to
the empty value (clears that filter). Selected row: `bg-rose/12 text-rose` + a check icon.
Keyboard-highlighted row: subtle rose wash.

**Behaviour** — click / Enter / Space / ArrowDown opens; click-outside (document mousedown)
and Escape close; ArrowUp/Down + Home/End move the highlight (auto-scrolled into view);
Enter/Space or click commits and returns focus to the trigger.

**Accessibility** — combobox/listbox/option roles, `aria-selected`, `aria-controls`,
`aria-label`; a subtle **rose focus ring** (`focus-visible:ring-rose/40`) replaces the harsh
native blue outline; readable contrast in both themes.

## 6. Light / dark mode
Both verified via Playwright screenshots on `/sales`:
- **Light:** white/rose pills, rounded-2xl menu with soft shadow, rose-selected "All market"
  row with check, chevron flipped on the open trigger.
- **Dark:** raised dark menu surface (`--surface-raised` = `30 36 46`) with strong contrast,
  rose accent preserved, readable options. All colors are CSS-variable tokens, so theme
  switching is automatic.

## 7. Mobile responsiveness
Verified at 390 px: filter pills wrap cleanly into rows; an open menu stays fully within the
viewport (left-aligned, width-capped); **`scrollWidth == clientWidth` (390 == 390) → no
horizontal overflow**. Chips and "Clear all" wrap neatly.

## 8. Filter functionality verification (Playwright, `/sales`)
| Check | Result |
|---|---|
| Market menu opens on click | ✅ |
| Selecting "UAE" updates the trigger label | ✅ |
| **Market → City dependency** (City options after UAE) | ✅ `All city, Dubai, Abu Dhabi, Sharjah` |
| Active chips appear (Market: UAE · City: Dubai) | ✅ |
| Escape closes the menu | ✅ |
| Click-outside closes the menu | ✅ |
| "Clear all" resets chips | ✅ |
| Mobile 390 px — no horizontal overflow | ✅ (390 == 390) |
| Console errors | ✅ none (excluding the offline WhatsApp-agent connection, unrelated) |

Filters still re-slice the data views (the engine in `lib/dashboard/filters.ts` is
untouched); chips, Clear all, and the market/city dependency all work exactly as before.

## 9. Tests / checks run (honest)
- **`tsc --noEmit`:** ✅ 0 errors.
- **`next build`:** ✅ **Compiled successfully** + type-check clean + **all 24 static pages
  generated**, but the command then exits non-zero on a **Windows-only filesystem race**
  renaming the framework's auto-generated `.next/export/500.html → server/pages/500.html`
  (`ENOENT`, Defender file-lock). Reproduced identically twice; it is unrelated to this
  change (React-only, no pages/router or config edits) and pre-exists it. Compilation and
  type-checking — the parts this change could affect — pass.
- **Runtime / Playwright:** ✅ full functional + visual verification on the dev server
  (light, dark, mobile) — see §6–8.

## 10. Known limitations
- The production `next build` cannot be shown fully green in this Windows environment due to
  the `500.html` rename race (§9). Runtime behavior is verified instead.
- The dropdown is a single-select listbox (matches every current filter). Multi-select and
  type-ahead search are not implemented (not needed today; the component is small to extend).
- Right-edge auto-flip uses a viewport-width heuristic (trigger past 60% → right-align) rather
  than full collision detection; sufficient for the current filter-bar layout.

## 11. Recommended next step
If future filters grow long option lists (e.g. facilities, drivers), add optional type-ahead
search inside the same `FilterSelect` (a filter input above the option list) — the listbox
plumbing is already in place. Otherwise no follow-up required.
