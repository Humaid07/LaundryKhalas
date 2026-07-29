# ERP Dashboard Redesign — Phase 0: Audit & Design Proposal

- **Date:** 2026-07-29
- **Scope:** `apps/admin` only (internal admin dashboard). No backend / agents / other apps / `supabase/`.
- **Status:** Proposal — **owner decisions locked (see §8); awaiting explicit green light to start Phase 1**. No component code written in this phase.
- **Governing rules:** CLAUDE.md §10 (Admin UI), §19 (UI Design Standard), §11–13 (docs), §15 (git safety).
- **Related docs:** [[minimal-dashboard-design-system]], [[dashboard-filter-system]], [[dashboard-navigation]], [[admin-ui-architecture]], [[internal-dashboard-ui]].

> **What this is:** the plan you approve before any code changes. It inventories the current design system, then specifies the extended tokens, elevation scale, card-variant catalog, module-accent model, and the filters/nav declutter approach — with exact values and before/after mockups.

---

## 1. Objective

Evolve a competent-but-flat SaaS dashboard into a **modern ERP operations cockpit**: clearer module identity, a shared page grammar every module obeys, richer-but-restrained colour (rose stays the master brand), stronger surface/border definition, a small deliberate set of card variants, and a decluttered filter/nav layer — all built so **new modules drop in as config + composition, not new one-off CSS.**

---

## 2. Audit — what exists today

### 2.1 Token architecture (strong; keep and extend)

- Tokens in `app/globals.css` as `R G B` triplets; `tailwind.config.ts` maps them to semantic Tailwind colours via a `token()` helper with `<alpha-value>` support. Light **and** dark both defined.
- **Zero hardcoded hex** anywhere in `components/dashboard` or the page tree — colour flows through tokens (`text-ink`, `bg-rose/12`, …) and the `CHART.*` palette in `lib/dashboard/chart-theme.ts`. Charts recolour on theme switch with no JS.
- Governing idea already in the CSS header comment: **"Pink is a signal, not a fill."** Rose is reserved for brand / active / primary / one hero chart hue.

**Current base tokens**

| Token | Light `R G B` | Dark `R G B` |
|---|---|---|
| `--canvas` | 250 247 248 | 13 15 19 |
| `--surface` | 255 255 255 | 22 27 34 |
| `--surface-2` | 252 250 251 | 28 34 43 |
| `--surface-raised` | 255 255 255 | 30 36 46 |
| `--border` | 236 231 234 | 40 46 56 |
| `--border-strong` | 222 214 219 | 57 65 77 |
| `--ink / -muted / -faint` | 26 20 24 / 107 99 104 / 150 143 148 | 237 233 236 / 158 164 174 / 112 119 129 |
| `--rose / -strong / -contrast` | 214 51 108 / 180 45 94 / 255 255 255 | 232 76 136 / 240 106 162 / 20 12 16 |
| semantic `--success/-warning/-danger/-info` | 5 150 105 / 217 119 6 / 220 38 38 / 37 99 235 | 52 211 153 / 251 191 36 / 248 113 113 / 96 165 250 |
| chart `--c-rose/-plum/-teal/-amber/-slate/-sky` | (see globals.css) | (see globals.css) |

Existing `boxShadow` tiers in Tailwind: `card`, `raised`, `pop`, `rose-glow`. Radii `lg/xl/2xl/3xl`. Motion `ease-out-quint`, `.lk-enter`, `.lk-menu-in`. Reduced-motion handled.

### 2.2 Shell & layout

- `shell/Sidebar.tsx` — expandable parent/child tree, derived from `nav.ts` → `sections.ts`. Active state always **rose**. Role-filtered via `isRouteAllowed`.
- `shell/Topbar.tsx` — search input with a **⌘K hint that currently does nothing**, theme toggle, notifications, user menu.
- `shell/PageHeader.tsx` (`ResponsivePageHeader`) — eyebrow (rose) + title + description + actions + optional `<FilterBar/>`.
- `shell/FilterBar.tsx` + `FiltersProvider.tsx` — 6 always-visible pill dropdowns (Date, Region, Market, City, Channel, Service) in a bordered bar; Region→Market→City cascade; active-filter chips already exist. **Provider contract:** `filters, setFilter, clearFilter, clearAll/clear, marketOptions, cityOptions`.

### 2.3 Component kits — the central fact

Two visual languages coexist:

| Kit | Components | Used by |
|---|---|---|
| **Standard analytics** | `StatCard`/`StatGrid`, `ChartCard`, `DataTable`, `Panel`/`PanelHeader`, `charts` (Area/Donut/Bar/Grouped) | overview, sales, orders |
| **Minimal progressive-disclosure** (`components/dashboard/minimal/`) | `MinimalKpiStrip`, `CompactRecordCard`/`RecordList`, `DataPreviewTable`, `WorkflowTabs`, `DetailPageShell`, `DetailColumns`, `Field`/`FieldGrid`/`Chip`, `ActionMenu`, `ViewDetailsButton` | operations (subs), marketing, seo-agents, partner-acquisition, dev-automation, reports, settings |
| **Hybrid** | both | **finance-compliance** (one router, two languages — a seam to unify) |

### 2.4 Landing patterns — two outliers

- **Config-driven** `SectionLanding` (card grid of `SectionCard`s from `sections.ts`) — used by 8 modules. This is the pattern to standardise on.
- **Bespoke** `overview/page.tsx` (~218 lines, fully hand-built, filter-aware) — the richest one-off.
- **Bespoke** `OperationsOverview` — a *second* hand-built landing that diverges from `SectionLanding`.

### 2.5 Module map (11 top-level nav items)

`Overview` (bespoke, no subs) · `Operations` (hybrid landing + minimal subs, deepest nesting) · `Orders` (standard, single page) · `Sales` (standard) · `Partner Acquisition` (minimal, cols:4) · `SEO Agents` (minimal) · `Marketing` (minimal) · `Finance & Compliance` (hybrid) · `Dev & Automation` (minimal) · `Reports` (minimal) · `Settings` (minimal, `filterable:false`).

### 2.6 Honest assessment of the gaps (what "flat" means)

1. **Low surface definition in light mode** — `surface` and `surface-raised` are both pure white; `border` (236 231 234) on `canvas` (250 247 248) is ~2–3% contrast. Cards melt into the canvas; no real elevation.
2. **No module identity** — every accent is rose; nothing tells you *which* domain you're in except the title.
3. **Card monotony** — most things are the same white `rounded-2xl border shadow-card` box; a page reads as a wall of identical rectangles with no hierarchy between a headline metric and a supporting one.
4. **Filter wall** — 6 permanent dropdowns on every filterable page consume a full row and read as heavy.
5. **Two design languages** — standard vs. minimal, plus two bespoke landings, mean "which component do I use?" isn't obvious for the next module.

---

## 3. Proposal

### 3.1 Extended token set

All new colours are tokens (light **and** dark). Rose is unchanged (still the master brand).

**A) Warmer, more layered light surfaces + stronger borders** (dark gets a light touch-up):

| Token | Light — current → **proposed** | Dark — current → **proposed** | Why |
|---|---|---|---|
| `--canvas` | 250 247 248 → **248 244 246** | 13 15 19 → *(unchanged)* | Deeper warm rose-white so white cards read as elevated. |
| `--surface` | 255 255 255 → *(unchanged)* | 22 27 34 → *(unchanged)* | Cards stay crisp; now pop against the warmer canvas. |
| `--surface-2` | 252 250 251 → **249 245 247** | 28 34 43 → *(unchanged)* | Warmer inset for wells/table interiors. |
| `--surface-sunken` *(new)* | **244 239 242** | **17 21 27** | Deepest layer (page wells behind cards, KPI band bg). |
| `--surface-raised` | 255 255 255 → *(unchanged)* | 30 36 46 → *(unchanged)* | Elevation via shadow, not colour, in light. |
| `--border` | 236 231 234 → **230 222 226** | 40 46 56 → **44 51 62** | Visible-but-tasteful definition. |
| `--border-strong` | 222 214 219 → **212 201 208** | 57 65 77 → **60 69 82** | Clear dividers / raised-tier borders. |

**B) Module-accent tokens (new).** A tightly-curated set of 4 accent hues + brand rose — reused via *families* (see §3.4). Each appears only in small wayfinding surfaces (nav active, page eyebrow, icon chip, section header rule), never as a status colour. **Green and pure-amber-as-warning hues are deliberately avoided** so accents never read as `success`/`warning`.

| Accent token | Light `R G B` (hex) | Dark `R G B` (hex) |
|---|---|---|
| `--rose` *(exists, brand)* | 214 51 108 (#d6336c) | 232 76 136 (#e84c88) |
| `--accent-teal` *(new)* | 13 148 136 (#0d9488) | 45 212 191 (#2dd4bf) |
| `--accent-amber` *(new)* | 194 120 3 (#c27803) | 251 191 36 (#fbbf24) |
| `--accent-violet` *(new)* | 124 58 237 (#7c3aed) | 167 139 250 (#a78bfa) |
| `--accent-slate` *(new)* | 71 85 105 (#475569) | 148 163 184 (#94a3b8) |

Tailwind mapping (Phase 1): add `surface.sunken`, keep `border`/`border-strong`, and add an `accent` colour object (`accent.teal/amber/violet/slate`) via the same `token()` helper so `bg-accent-teal/12`, `text-accent-violet`, `ring-accent-amber/20` all work with `<alpha-value>`.

### 3.2 Elevation scale (formalised)

A documented 4-level scale mapping to the **existing** shadow tokens — no new shadow primitives needed, just a rule for when to use each:

| Level | Name | Recipe | Use |
|---|---|---|---|
| 0 | **Sunken / flat** | `bg-surface-2` or `surface-sunken`, no shadow | Table interiors, inset wells, the KPI-band background. |
| 1 | **Card** | `bg-surface border-border shadow-card` | Standard Panel / StatCard / ChartCard — the default. |
| 2 | **Raised** | `bg-surface border-border-strong shadow-raised` | Hero KPI, the one key panel per page, hovered cards. |
| 3 | **Popover** | `bg-surface-raised border-border-strong shadow-pop` | Menus, FilterSelect dropdown, ⌘K palette, tooltips. |

The deeper `canvas` + white `surface` gives level-1 cards real presence in light mode *without* heavier shadows; level 2 adds `border-strong` + `shadow-raised` so a hero reads as lifted even at rest.

### 3.3 Card-variant catalog (small, deliberate, reuse-first)

This is **not** a new bespoke component per page. It is the existing components + one new variant + an `accent` prop, each with a documented "when to use."

| # | Variant | Component | Anatomy | When to use |
|---|---|---|---|---|
| 1 | **Standard KPI** | `StatCard` *(exists)* | eyebrow · big mono number · `DeltaChip` · sparkline; rose→**accent** hover rail | Metric grids (`StatGrid`). |
| 2 | **Hero KPI** *(new variant of StatCard, `variant="hero"`)* | spans 2 cols; **solid module-accent top-rule** (not hover-only); larger number; optional inline mini-trend + one secondary stat | The single headline metric of a page (Orders on Overview, Revenue on Finance). |
| 3 | **Panel** | `Panel`/`PanelHeader` *(exists; add optional `accent`)* | accent hairline top-rule + accent-tinted header icon chip when `accent` set | Charts, lists, tables — the workhorse container. |
| 4 | **Chart card** | `ChartCard` *(exists; inherits Panel `accent`)* | Panel + title/subtitle + chart body | Any chart. |
| 5 | **Module landing card** | `SectionCard` *(exists; restyle)* | **module-accent** icon chip + accent hairline top-rule + accent hover border (currently hardcoded rose) | Section landing grids. |
| 6 | **Compact record card** | `CompactRecordCard` *(exists)* | id · title · one status badge · ≤3 fields · chevron | Minimal list pages (progressive disclosure — unchanged). |

Net new code is small: a `hero` variant on `StatCard`, an `accent` prop threaded through `Panel`/`SectionCard`, and accent tokens. Everything else is reuse.

### 3.4 Module accent map — *recommended: families (5 accents total)*

Ten unique hues fight the constraints (avoiding green=success and amber=warning leaves mostly the cool→magenta arc, which forces a muddy rainbow). The disciplined ERP answer — and what SAP Fiori / Oracle Redwood actually do — is **accent families**: a few hues, each shared by a domain family. This is maximally restrained, harmonious, and **extends for free** (a new module joins a family).

| Family | Accent | Modules |
|---|---|---|
| **Command** | `rose` (brand) | Overview |
| **Fulfilment** | `accent-teal` | Operations, Orders |
| **Revenue** | `accent-amber` | Sales, Finance & Compliance |
| **Growth** | `accent-violet` | Marketing, SEO Agents, Partner Acquisition |
| **System / utility** | `accent-slate` | Dev & Automation, Reports, Settings |

Each module still gets a distinct identity via its **lucide icon** + family accent (icon chip, eyebrow, active nav rail, landing-card rule). Utility modules staying chromatically quiet is intentional, not a gap.

**Implementation:** one source of truth — `lib/dashboard/accents.ts` exporting `MODULE_ACCENT: Record<moduleKey, AccentName>` and a helper `accentClasses(name)` → the chip/text/rule/ring class strings. Consumed by `Sidebar`, `PageHeader`, `SectionCard`, and the hero KPI. Nothing per-page.

> **Alternative (documented, not recommended):** if you want every module chromatically unique, we add 3 more hue tokens (`sky`, `indigo`, `fuchsia`) and remap `MODULE_ACCENT` 1:1. The token/helper architecture supports either with no structural change — it's a values-only decision you can flip later. I recommend families for the ERP "restrained colour-coding" look.

### 3.5 Filters & nav declutter

**Filters — recommended:** replace the 6-pill wall with **one "Filters" button** (with an active-count badge, e.g. `Filters · 2`) that opens a **popover** containing the same six controls, grouped: *Time* (Date) · *Geography* (Region→Market→City cascade) · *Scope* (Channel, Service). Next to the button, keep the **active-filter chip row** (already built in `FilterBar`) always visible so what's scoped stays glanceable and one-click clearable.
- **Contract preserved 100%:** same `FiltersProvider` (`setFilter`/`clearFilter`/`clearAll`, `marketOptions`/`cityOptions` cascade) and the same accessible `FilterSelect` components — just relocated into a popover.
- **A11y:** button `aria-expanded`/`aria-controls`; focus moves into the popover and is trapped; `Esc` closes; `FilterSelect` keyboard/roving behaviour unchanged; reduced-motion respected.

**⌘K command palette — recommended (biggest single declutter win):** the Topbar already renders a ⌘K hint that does nothing. Wire it to a command palette for **navigation** (jump to any section/subsection — reachable without hunting the sidebar tree) and quick filter/search actions. This lets us lean less on deep sidebar nesting.

**Nav — LOCKED: keep the sidebar flat (no group labels).** Keep the config-driven tree (`nav.ts`/`sections.ts` and the *derived-children* contract are untouched). Declutter *without* group headers by: (a) collapsing children by default and relying on landing pages + ⌘K for depth; (b) colouring the active item with its **module accent** instead of always-rose, for wayfinding. *(The Command · Operate · Grow · System grouping was considered and declined — the flat list of 10 stays.)*

Rationale summary: the wall → a button + chips removes a full heavy row while keeping scope glanceable; ⌘K modernises navigation and reduces sidebar dependence; sidebar grouping adds structure without touching routes. All choices keep the provider contract and full keyboard/SR accessibility.

---

## 4. Before / After mockups

### 4.1 Overview page

```
BEFORE  (flat: rose-only, cards blend into canvas, 6-pill filter wall)
┌───────────────────────────────────────────────────────────────────────┐
│ OPERATIONS · GCC            (rose eyebrow)          [Export] [New Inbound]│
│ Command Center                                                          │
│ A live snapshot of orders, revenue, agents...                           │
│ ┌── Filters: [Date▾][Region▾][Market▾][City▾][Channel▾][Service▾] ──┐   │  ← 6-pill wall
│ └────────────────────────────────────────────────────────────────────┘  │
│ Headline totals                                        (Overall snapshot)│
│ ┌ KPI ┐ ┌ KPI ┐ ┌ KPI ┐ ┌ KPI ┐   ← 4 identical white boxes, faint edge  │
│ └─────┘ └─────┘ └─────┘ └─────┘                                          │
│ ┌ Orders over time ......2col ┐ ┌ Revenue & profit ┐                    │
│ └──────────────────────────────┘ └──────────────────┘                   │
└───────────────────────────────────────────────────────────────────────┘

AFTER  (ERP: rose command-accent, layered surfaces, one filter button)
┌───────────────────────────────────────────────────────────────────────┐
│ ▸ Command / Overview        (breadcrumb)                                │
│ ◗ COMMAND CENTER            (rose eyebrow + rose icon chip)              │
│ Live snapshot across every market        [⚲ Filters · 2] [Export] [+New]│  ← 1 button + count
│ ┌ Region: Dubai ✕ ┐ ┌ Service: Dry Clean ✕ ┐   ← active chips only      │
│ ╔═══════════════════════════╗ ┌ KPI ┐ ┌ KPI ┐   ← HERO KPI (rose top-  │
│ ║ ▮ ORDERS TODAY            ║ └─────┘ └─────┘      rule, lifted) + std   │
│ ║ 1,284  ↑8.2%  ╱╲╱ trend   ║ ┌ KPI ┐ ┌ KPI ┐      cards on sunken band │
│ ╚═══════════════════════════╝ └─────┘ └─────┘                           │
│ ┌ Orders over time ...2col ┐ ┌ Revenue & profit ┐  ← cards read raised  │
│ └──────────────────────────┘ └──────────────────┘    on deeper canvas   │
└───────────────────────────────────────────────────────────────────────┘
```

### 4.2 Module landing page (e.g. Sales — Revenue/amber family)

```
BEFORE  (SectionLanding: identical white cards, rose icon chips everywhere)
┌───────────────────────────────────────────────────────────────────────┐
│ REVENUE & GROWTH (rose)                                        [Export] │
│ Sales                                                                   │
│ ┌ [rose▢] Sales Overview  ┐ ┌ [rose▢] Markets   ┐ ┌ [rose▢] Channels ┐  │
│ │ desc...                 │ │ desc...           │ │ desc...          │  │
│ │ [AED 612K][+11.2%]      │ │ [UAE][6]          │ │ [WhatsApp][5]    │  │
│ │                 Open →  │ │           Open →  │ │          Open →  │  │
│ └─────────────────────────┘ └───────────────────┘ └──────────────────┘  │
└───────────────────────────────────────────────────────────────────────┘

AFTER  (module = amber "Revenue" family: amber eyebrow/chip/rule; layered)
┌───────────────────────────────────────────────────────────────────────┐
│ ▸ Revenue / Sales                          [⚲ Filters] [Export]         │
│ ◗ SALES  (amber eyebrow + amber icon chip)                              │
│ ──────── amber section rule ───────────────────────────────────────────│
│ ┌▔amber▔▔▔▔▔▔▔▔▔▔▔▔┐ ┌▔amber▔▔▔▔▔▔▔┐ ┌▔amber▔▔▔▔▔▔▔┐   ← accent top-rule │
│ │ [amber▢] Sales   │ │ [amber▢]    │ │ [amber▢]    │      + amber chip   │
│ │ Overview         │ │ Markets     │ │ Channels    │      + hover border │
│ │ AED 612K  +11.2% │ │ UAE   6     │ │ WhatsApp 5  │        = amber      │
│ │           Open → │ │      Open → │ │      Open → │                     │
│ └──────────────────┘ └─────────────┘ └─────────────┘                     │
└───────────────────────────────────────────────────────────────────────┘
```

The page grammar every module obeys: **breadcrumb → accented header (eyebrow + icon chip + rule) → [filter button + chips] → KPI band (hero + standard on a sunken well) → content**.

---

## 5. What is mock-only / live / deferred

- **Mock-only:** all data stays from `lib/dashboard/mock-data.ts` and `sections.ts`. No new operational numbers, prices, or records invented. MOCK-mode / staged indicators stay visible per repo convention.
- **Live:** nothing — this is presentation-layer only; no backend, agent, or integration change.
- **Deferred (explicitly out of scope):** URL-syncing the filters (already a documented next step), any data-contract change, the per-module-unique-hue alternative, and touching the two live-WhatsApp views' behaviour.

## 6. Security / privacy

No change to data flow. PII masking (`maskPhone`, area-only) and the privacy firewall are untouched — this is styling and layout only.

## 7. Risks & guardrails

- **Contract preservation** is the main risk: the plan keeps `FiltersProvider`, `nav.ts`/`sections.ts` (derived children), all routes, and `FilterSelect` a11y intact. Verified per phase with `tsc`, `lint`, `build`, and light/dark render checks.
- **Git (§15):** LOCKED — work proceeds **on `main`** (owner chose to keep the standing commit-to-main preference over a feature branch). Changes stay tightly scoped to `apps/admin`; **no commits until you ask**.
- **No overbuild:** additions are 4 accent tokens + 2 surface tokens, one `hero` variant, one `accent` prop, one `accents.ts` map, a filter popover, and a ⌘K palette — small and reviewable.

## 8. Decisions — LOCKED (2026-07-29)

1. **Accent model:** ✅ **Families (5 accents)** — Command=rose, Fulfilment=teal, Revenue=amber, Growth=violet, System=slate.
2. **⌘K palette:** ✅ **Include in Phase 1** — wire the existing Topbar ⌘K affordance to a nav + quick-action palette.
3. **Sidebar grouping:** ✅ **Keep flat** — no group labels; declutter via accents + collapsed children + ⌘K only.
4. **Git:** ✅ **Work on `main`** (not a feature branch); no commits until asked.

---

## 9. Tests run

None — Phase 0 is a written proposal with **no code changes**. Lint/typecheck/build gates apply from Phase 1 onward.

## 10. Next recommended step

On approval (and answers to §8), proceed to **Phase 1 — Design tokens + shell**: implement the extended tokens, restyle the shell with the page grammar + module accents, and ship the filter declutter (+ ⌘K if approved), verified in both themes. Then a Phase 1 build report and stop for review.
