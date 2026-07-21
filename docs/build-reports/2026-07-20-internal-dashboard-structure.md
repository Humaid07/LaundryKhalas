# Build Report — Internal Dashboard Structure

**Date:** 2026-07-20
**Module:** Internal Operations Dashboard (command center)
**App:** `apps/admin` (Next.js, port 3000)
**Status:** ✅ Built, typechecked, built, and browser-verified. Mock-only.

---

## 1. Task objective

Build the **real internal dashboard structure** for LaundryKhalas: the shell,
layout, navigation, eight top-level sections, responsive UI, dark mode, and a
clean, premium, non-generic design system — all on mock data. No backend
logic, no live APIs, no secrets. Frontend/structure first; individual features
get built out on top of this in later tasks.

## 2. What was built

A complete internal **Command Center** with a persistent app shell (sidebar +
topbar + filter bar), a rose/white design system with full dark mode, a
reusable component library, LaundryKhalas-specific mock data, and all eight
section pages with KPIs, charts, tables and panels.

## 3. Why it was built

This becomes the daily command surface for ops, sales, marketing, SEO and
finance, and the visual home the WhatsApp Agent, Classifier, and future agents
plug into. Structure-first means every later feature has a consistent, polished
place to live.

## 4. Design inspiration used

- **Lovable** and **Bolt** were used **only as visual/UX reference** during the
  session (layout density, card/chart rhythm, dashboard IA). No code was copied
  from either, and **no magic link / token / URL was saved into these docs** (per
  explicit instruction — the Lovable link is a private magic link).
- **Old prototype** (`D:\LaundryKhalas\LaundryKhalaasPrototype`) referenced for
  product concepts only, not copied.
- The `frontend-design` skill guided the deliberate, non-templated direction.

### How the result improves on all three
- **Rose is a signal, not a fill** — reserved for brand, active states, primary
  actions and one hero chart hue; surfaces stay clean. Avoids the "tacky pink"
  and generic-SaaS trap.
- **Deliberate type trio** (Bricolage Grotesque / Plus Jakarta Sans / Space
  Grotesk) instead of Inter/Roboto/Arial.
- **One design system, light + dark**, driven by CSS variables so charts
  recolor instantly on theme switch (verified: dark charts resolve to the
  dark-mode rose).
- **Genuinely responsive** — tables convert to cards on mobile; collapsible +
  drawer sidebar.

## 5. Pages created (routes)

All under the `(dashboard)` route group in `apps/admin/app`:

| Route | Page | Highlights |
|---|---|---|
| `/overview` | Command Center | 12 KPI cards, 6 charts, latest orders, approvals, conversations, activity |
| `/operations` | Operations | Tabs: WhatsApp Agent (chat preview), Orders, Tickets, Driver Assignment, Order Changes |
| `/sales` | Sales | 10 KPIs, acquisition/B2B-B2C/market/channel/service charts, top cities/services/customers |
| `/seo-agents` | SEO Agents | Daily brief, 10 KPIs, GSC/index/pipeline charts, 14 agent cards, task table |
| `/marketing` | Marketing | 8 tabs incl. Platform Analytics, Content Calendar, **AI Creative Studio**, Approval Queue |
| `/finance` | Finance | 12 KPIs, revenue-vs-cost, profit trend, cost donut + breakdown table |
| `/reports` | Reports | 7 report cards + a structured report viewer |
| `/settings` | Settings | Profile, team, roles, markets, notifications, agent guardrails, connected apps, theme |

`/` now redirects to `/overview`. Legacy `/admin/*` pages are **untouched and still build**.

## 6. Components created

**Shell** (`components/dashboard/shell/`): `AppShell`, `Sidebar`, `Topbar`,
`FilterBar`, `ThemeToggle`, `PageHeader` (`ResponsivePageHeader` + `SectionTitle`), `Brand`.

**UI primitives** (`components/dashboard/ui/`): `Panel`/`PanelHeader`,
`StatusBadge`, `Eyebrow`, `DeltaChip`, `Sparkline`, `StatCard`/`StatGrid`,
`ChartCard`, `DataTable` (responsive), `Button`, `Tabs`, `Switch`,
`EmptyState`/`LoadingState`/`Skeleton`, `tones` helper.

**Charts** (`components/dashboard/charts.tsx`): `AreaTrend`, `LineTrend`,
`BarSeries`, `GroupedBars`, `DonutChart` (Recharts).

**Widgets** (`components/dashboard/widgets.tsx`): `AgentStatusCard`,
`ApprovalCard`, `ActivityTimeline`, `ReportCard`, `PlatformMetricCard`,
`FinanceBreakdownCard`, `ConnectedAppRow`, `MiniMetric`.

**Feature**: `CreativeStudio` (interactive, mock AI creative composer).

## 7. Files created / modified

**Created (~30):** all files under `app/(dashboard)/`, `components/dashboard/`,
and `lib/dashboard/` (`nav.ts`, `types.ts`, `formatters.ts`, `chart-theme.ts`,
`status-maps.ts`, `mock-data.ts`, `theme-provider.tsx`).

**Modified (5):** `app/layout.tsx` (fonts + ThemeProvider), `app/page.tsx`
(redirect to `/overview`), `app/globals.css` (design tokens), `tailwind.config.ts`
(rose theme + fonts, legacy aliases preserved), `package.json`
(added `recharts`, `next-themes`).

## 8. API endpoints added/changed

None. This is frontend/structure only. No network calls are made by the dashboard.

## 9. Database tables/models added/changed

None.

## 10. UI pages/components added/changed

See §5 and §6. New design system in `globals.css` + `tailwind.config.ts`.

## 11. Agent behavior added/changed

None. The UI *visually represents* agent states (WhatsApp, SEO, marketing
agents) and shows approval gates everywhere, but no agent logic runs here. The
existing WhatsApp Agent (`apps/whatsapp-agent`) is **not yet wired in** — that's
the next integration step.

## 12. Integrations added/changed

None live. All integrations (WhatsApp, Stripe, GSC, GA4, Semrush, Ahrefs,
Instagram, Facebook, TikTok, LinkedIn, HeyGen, Gamma, Composio, Apollo, Gmail)
appear as **placeholders** with status badges (Not connected / Coming soon /
Needs approval).

## 13. What is mock-only

**Everything.** All data comes from `lib/dashboard/mock-data.ts` (deterministic,
LaundryKhalas-specific). Filters, search, notifications, approve/reject buttons,
and the Creative Studio are visual/interactive but do not persist or call out.

## 14. What is live

Nothing. `Live WhatsApp: Off`, `Live Stripe: Off`, `Live LLM: Off` — surfaced in
the sidebar and Settings.

## 15. What is intentionally deferred

Real data wiring, working global filters (currently accessible but don't
re-slice data), wiring the WhatsApp Agent chat into Operations, real approval
workflow persistence, per-page detail routes/modals, auth/roles enforcement,
and all real third-party integrations.

## 16. Tests run

- `npx tsc --noEmit` (typecheck)
- `npm run build` (Next.js production build)
- Playwright browser sweep: all 8 routes in light, dark, and mobile viewports;
  console-error capture; chart-render + theme-recolor assertions.

## 17. Test results

- **Typecheck: PASS** (0 errors).
- **Build: PASS** — 18 routes compiled; all 8 dashboard routes prerendered
  static; legacy `/admin` routes still build. One **pre-existing** ESLint
  warning in legacy `app/admin/conversations/page.tsx` (not introduced here).
- **Browser: PASS** — **0 console errors** across all pages/themes/viewports.
  Charts render (140 SVG paths on Overview) and **recolor for dark mode**
  (dark charts resolved to `rgb(232, 76, 136)`). Mobile converts tables to
  cards with no horizontal overflow.

## 18. Bugs/issues found

- Changing global Tailwind tokens initially threatened legacy `/admin` styling
  (it used `brand`/`neutral`/`*-soft`/`*-text`). **Fixed** by restoring those as
  backward-compatible static aliases in `tailwind.config.ts`.
- Variable-font weight arrays in `next/font` were removed (all three faces are
  variable fonts; the full weight axis is included automatically).

## 19. Known limitations

- Global filters and search are presentational (don't filter mock data yet).
- Approve/Reject/Schedule buttons are non-persisting placeholders.
- No detail pages/modals for individual orders/tickets yet.
- Next.js is pinned at 14.2.18 (has a published advisory) — fine for local mock
  dev; bump before any deploy.

## 20. Security/privacy notes

- No secrets added; no `.env` values committed; **no Lovable magic link or token
  stored in docs**.
- Privacy firewall respected in the UI: phone numbers are **masked**
  (`maskPhone`) in conversation lists and previews; no full addresses shown.
- Every agent-generated action is shown behind an explicit **human approval**
  gate; mock-mode is always visible.

## 21. Cost/LLM usage notes

Zero. No LLM or external calls. Google Fonts are fetched at build time by
`next/font` and self-hosted in the build output.

## 22. Screens/pages to demo

Overview (light + dark), Operations → WhatsApp Agent tab, Marketing → AI
Creative Studio, SEO Agents (daily brief + fleet), Finance, and mobile Overview
(table-to-card). See `docs/presentation-notes/week-01-internal-dashboard-demo.md`.

## 23. Commands to run

```bash
cd "D:/Laundry Khalas App/apps/admin"
npm install          # first time (adds recharts, next-themes)
npm run dev          # http://localhost:3000  → redirects to /overview
npm run typecheck    # tsc --noEmit
npm run build        # production build
```

## 24. How to verify manually

1. Open `http://localhost:3000` → lands on `/overview`.
2. Toggle dark mode (sun/moon in topbar) — whole UI + charts recolor.
3. Click each sidebar section; confirm KPIs, charts, tables render.
4. Operations → tabs; Marketing → AI Creative Studio → "Generate preview".
5. Narrow the window to mobile — sidebar becomes a drawer, tables become cards.
6. Confirm the **MOCK ENVIRONMENT** badge (sidebar) and `Live … : Off` chips (Settings).

## 25. Next recommended step

**Wire the existing WhatsApp Agent (`apps/whatsapp-agent`, :8100) into the
Operations → WhatsApp Agent tab** so the chat preview and approval flow become
real end-to-end, then make the global filters actually re-slice data.
