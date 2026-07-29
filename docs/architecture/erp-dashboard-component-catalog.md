# ERP Dashboard — Component Catalog & Accent System

> Status: **active** · Introduced 2026-07-29 (ERP redesign Phase 2) · Applies to `apps/admin`, `app/(dashboard)/**`.
> Companion to [[minimal-dashboard-design-system]] (the progressive-disclosure rules) and the redesign build reports
> (`build-reports/2026-07-29-erp-dashboard-phase-*`). This doc is the "which component / which accent do I use?" reference
> that makes new modules cheap to add.

## 1. The accent system (section colour-coding)

Rose stays the master **brand** colour ("pink is a signal, not a fill") — logo, primary actions, active brand dot — and is intentionally **not** assigned to any section. Every top-level section carries **one distinct accent**, used only for wayfinding — nav (icon tint + active), page eyebrow, icon chip, section rule, card top-rule — **never** as a status colour (status uses `success/warning/danger/info`). Green/lime hues are avoided (they read as `success`).

> Updated 2026-07-29 (sidebar polish): moved from 5 shared **families** to **one unique hue per section** so each section has a persistent identity and the sidebar reads as distinct. Same architecture, richer map.

**Single source of truth:** `lib/dashboard/accents.ts`

- `MODULE_ACCENT: Record<routeSegment, AccentName>` — one line per section.
- `ACCENT_CLASSES: Record<AccentName, AccentClasses>` — literal Tailwind class bundles (`text`, `chip`, `rail`, `softBg`, `hoverBg`, `strongBg`, `ring`, `hoverBorder`, `dot`, `ctaHover`). Literals so the JIT compiler scans them — never build `bg-accent-${name}` dynamically.
- `accentForPath(pathname)` / `accentForHref(href)` → `AccentName`.
- `accentClasses(name)` / `accentClassesForPath(pathname)` → `AccentClasses`.
- Client hook: `lib/dashboard/use-accent.ts` → `useAccentName()` / `useAccentClasses()`.

**Section → accent (one hue each):**

| Section | Accent | Section | Accent |
|---|---|---|---|
| Overview | `slate` | SEO Agents | `indigo` |
| Operations | `teal` | Marketing | `fuchsia` |
| Orders | `sky` | Finance & Compliance | `cyan` |
| Sales | `amber` | Dev & Automation | `steel` |
| Partner Acquisition | `violet` | Reports | `plum` |
| — | — | Settings | `neutral` (gray) |

`rose` remains a valid `AccentName` for brand use but maps to no section.

**Adding a module:** add one line to `MODULE_ACCENT`. If it needs a brand-new hue, add the token in `globals.css` (light + dark) + `tailwind.config.ts` `accent.*` and a bundle in `ACCENT_CLASSES`; otherwise reuse an existing accent. The sidebar, header, sub-nav, and landing cards pick it up automatically.

**Tokens** (`globals.css`, light + dark; mapped in `tailwind.config.ts`): `--accent-{teal,amber,violet,slate,sky,indigo,fuchsia,cyan,steel,plum}` → `bg-accent-teal/12`, `text-accent-fuchsia`, `ring-accent-cyan/25`, … `neutral` uses the `ink` tokens. Changing `tailwind.config.ts` requires a **dev-server restart** (not hot-reloaded).

## 1a. Sidebar row structure

Every top-level nav row is a **fixed 4-column grid** so icons, labels, badges, and chevrons align regardless of content (`components/dashboard/shell/Sidebar.tsx`):

```
grid-cols-[24px_1fr_auto_18px]  ·  h-11  ·  gap-2.5  ·  rounded-xl
   │        │      │       └ chevron column — always reserved (icon only if the section has children)
   │        │      └ badge column — always present (empty span when no count)
   │        └ label — min-w-0 + truncate (+ title tooltip)
   └ icon — 18px, persistent section tint (opacity-60 → 100 on hover/active)
```

- **Hover:** section-tinted `accent.hoverBg` (soft) + icon brightens. **Active:** `accent.softBg` + accent text + accent icon + left `accent.rail` indicator + badge `accent.strongBg`.
- The submenu toggle is a **transparent hit target** absolutely positioned over the chevron column, so the chevron never nests in the anchor and its x-position never depends on label length. Chevron rotates (`rotate-180`) only when expanded.
- Nav is `overflow-x-hidden`; labels truncate → **no horizontal scrollbar**. Collapsed rail: centered icon + `title` tooltip, no label/badge/chevron.

## 2. Elevation scale

| Level | Name | Recipe | Use |
|---|---|---|---|
| 0 | Sunken | `bg-surface-2` / `bg-surface-sunken`, no shadow | Table interiors, inset wells, the KPI band background. |
| 1 | Card | `bg-surface border-border shadow-card` | Default container (Panel, StatCard, ChartCard). |
| 2 | Raised | `bg-surface border-border-strong shadow-raised` | Hero KPI, hovered cards, the one key panel per page. |
| 3 | Popover | `bg-surface-raised border-border-strong shadow-pop` | Menus, FilterSelect dropdown, FilterMenu, ⌘K palette, tooltips. |

## 3. Card & container variants

| Variant | Component (import) | Anatomy | When to use |
|---|---|---|---|
| **Standard KPI** | `StatCard` (`ui/StatCard`) | eyebrow · big mono number · `DeltaChip` · sparkline; accent hover-rail | Metric grids (via `StatGrid`). |
| **Hero KPI** | `HeroStat` (`ui/StatCard`) | solid accent top-rule + accent icon chip · very large number · delta · big sparkline **or** a `secondary` stat | The **one** headline metric of a page. Not more than one. |
| **KPI band** | `KpiBand` (`ui/primitives`) | sunken well wrapping a StatGrid; optional label + aside (e.g. `SnapshotBadge`) | The headline-metrics slot in the page grammar. |
| **Panel** | `Panel` / `PanelHeader` (`ui/primitives`) | container; optional `accent` → top-rule; `PanelHeader` optional `icon` → accent chip | Lists, tables, any grouped content. |
| **Chart card** | `ChartCard` (`ui/ChartCard`) | Panel + header (+ optional `accent`, `icon`) + chart body | Any chart. |
| **Module landing card** | `SectionCard` (`section/SectionCard`) | module-accent icon chip + top-rule + hover border + CTA | Section landing grids (auto-accented from `base`). |
| **Compact record card** | `CompactRecordCard` (`minimal/*`) | id · title · one status badge · ≤3 fields · chevron | Minimal list pages (progressive disclosure). Stays chromatically quiet — **no** module accent, per [[minimal-dashboard-design-system]] rule 3. |

**Accent props:** `StatCard`/`StatGrid`/`HeroStat`/`Panel`/`ChartCard`/`PanelHeader` all accept `accent?: AccentName` (default `rose`). In a client page: `const accent = useAccentName()` then pass it down.

## 4. Page grammar (every page)

```
breadcrumb  →  ResponsivePageHeader (accent eyebrow + icon chip)  →  KpiBand (Hero + StatGrid)  →  content (ChartCard / Panel / lists)
```

- `ResponsivePageHeader` (`shell/PageHeader`) auto-resolves the module accent + icon from the pathname; pass `breadcrumb` on landing pages (subsection pages get theirs from `SectionSubNav`).
- Analytics pages: KPI band + charts (standard kit). List pages: minimal kit (`MinimalKpiStrip` + `RecordList`), intentionally quiet.

## 5. Filters & navigation

- **`FilterMenu` + `FilterChips`** (`shell/FilterMenu`) — the consolidated global-filter control: one popover button with an active-count badge + an always-visible active-chip row. Rendered by `ResponsivePageHeader` when `showFilters`. Uses the unchanged `FiltersProvider` contract + accessible `FilterSelect`. **Prefer this** over the legacy inline `FilterBar`.
- **`CommandPalette`** (`shell/CommandPalette`) — ⌘K / Ctrl+K (or click the Topbar search) to jump to any section/subsection. Accent-coded, keyboard-driven.
- **Sidebar** — flat list of 10 (no group labels, by decision); active item uses the module accent.

## 6. Do / don't

- **Do** route all colour through tokens + `accents.ts`. **Don't** hardcode hex or build accent class names dynamically.
- **Do** use exactly one `HeroStat` per page. **Don't** turn every KPI into a hero.
- **Do** keep minimal list pages quiet (one status badge, ≤3 fields, no module accent on record cards).
- **Do** verify both themes and restart the dev server after `tailwind.config.ts` changes.
