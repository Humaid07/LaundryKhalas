# Build Report — Card hover glow, sidebar single-open accordion, open-in-new-tab

**Date:** 2026-07-30

## Objective
Three admin-dashboard UX improvements requested after the section-landing Spotlight cards:
1. A tuned hover treatment on cards **throughout** the dashboard (esp. Agent Fleet, which
   had no hover feedback), that adds a highlight/glow **without obscuring any info**.
2. Sidebar sections behave as a **single-open accordion** — opening one collapses the others.
3. An option to **open a section or subsection in a new tab**.

## What was built
### 1. Tuned card hover glow (CSS-only, universal)
- New `.lk-hover-glow` utility in `app/globals.css`: on hover it shows a **clearly visible
  brand-rose glow** — a rose ring + a spreading halo (no offset, so it reads as a glow on the
  DARK theme too, where a plain shadow is invisible) + a soft depth shadow — plus a firmer
  border. **Theme-aware**, **reduced-motion safe**, obscures no content. This is the CSS-only
  counterpart to the pointer-tracked `SpotlightCard` used on the section landings.
- Interactive `CompactRecordCard` (Agent Fleet + record cards) additionally lightens its
  background (`hover:bg-surface-2`) for an unmistakable highlight.
- **Note:** an earlier version used a neutral dark elevation shadow, which was ~invisible on the
  dark theme (the house `--shadow-color` is black); switched to the rose halo above.
- Applied at the **shared-component** level so it lands everywhere at once:
  `Panel` (→ every panel + `ChartCard`), `StatCard`, `HeroStat`, and the interactive
  `CompactRecordCard` (→ the Agent Fleet cards + most record cards across the dashboard).
  Passive content groupings (`DetailSectionCard`) were intentionally left alone.

### 2. Sidebar single-open accordion
- `Sidebar.tsx` now owns the open state: `openHref` (one section), defaulting to the section
  that contains the current route. Toggling a section opens it and **collapses the previously
  open one**; navigating into a section opens it (a manual collapse within the same route
  persists). `ParentRow` is now controlled (`expanded` + `onToggle` props) instead of holding
  its own state.

### 3. Open in a new tab (REMOVED per feedback)
- A hover `↗` "open in new tab" control was added, then **removed** at the user's request (they
  disliked it and it overlapped the chevron). Native open-in-new-tab still works on the child
  subsection links via Ctrl/Cmd+click or middle-click.

## Files changed
- `apps/admin/app/globals.css` — `.lk-hover-glow`.
- `apps/admin/components/dashboard/ui/primitives.tsx` — `Panel` gains the glow.
- `apps/admin/components/dashboard/ui/StatCard.tsx` — `StatCard` + `HeroStat` gain the glow.
- `apps/admin/components/dashboard/minimal/CompactRecordCard.tsx` — interactive variant gains the glow.
- `apps/admin/components/dashboard/shell/Sidebar.tsx` — accordion state + `NewTabButton` (parent + child).

## Tests / verification
- **Typecheck clean; lint clean** apart from the one pre-existing unrelated warning.
- Playwright: **accordion** — opening Marketing collapses Sales (aria-expanded + visibility);
  **new-tab** — parent + child buttons present and visible on hover; **glow** — `/overview`
  has 22 `.lk-hover-glow` elements and the box-shadow changes on hover; `/seo-agents/agent-fleet`
  has 16 fleet cards all carrying the glow with the hover shadow activating. Verified light + dark.

## Notes / scope
- Glow scope covers the interactive/entity + KPI + panel cards (the "cards" users interact with).
  Passive detail-page section blocks are excluded to avoid hover noise.
- Uncommitted at time of writing.
