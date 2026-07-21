# ADR — Internal Dashboard Design System

**Date:** 2026-07-20
**Status:** Accepted
**Context:** Building the real internal dashboard structure for LaundryKhalas.

## Decisions

### 1. Build inside `apps/admin`, not a new app
The internal dashboard extends the existing admin app in a `(dashboard)` route
group. Legacy `/admin/*` pages are preserved and still build. Avoids a duplicate
frontend and a second dev server.

**Consequence:** shared Tailwind/token layer; legacy color tokens kept as
backward-compatible static aliases.

### 2. Rose is a signal, not a fill
Pink/white identity is delivered by reserving rose for brand, active states,
primary actions and one hero chart hue — surfaces stay clean (warm-white in
light, deep slate in dark). This is the deliberate answer to "avoid tacky pink /
generic SaaS."

**Rejected:** pink backgrounds, pink gradients everywhere, glassmorphism.

### 3. CSS-variable tokens with `<alpha-value>` triplets
All semantic colors are `R G B` triplets in `:root` / `.dark`, mapped in Tailwind
as `rgb(var(--x) / <alpha-value>)`. One source of truth for both themes; opacity
utilities work; **charts recolor on theme switch for free** because chart colors
are `rgb(var(--c-*))`.

**Consequence:** verified that `var()` in Recharts `fill`/`stroke` presentation
attributes resolves in modern browsers (dark charts render the dark rose value).

### 4. Deliberate type trio (no Inter/Roboto/Arial)
Bricolage Grotesque (display) + Plus Jakarta Sans (body) + Space Grotesk
(numeric/tabular), via `next/font` (self-hosted, no runtime fetch, no external
call). Numeric face + tabular-nums gives KPIs an engineered feel.

### 5. Recharts for charts
Chosen for React/SSR fit and small footprint vs. the existing stack. Thin
wrappers (`AreaTrend`, `LineTrend`, `BarSeries`, `GroupedBars`, `DonutChart`)
keep pages declarative.

### 6. `next-themes`, class strategy
Standard, SSR-safe, `disableTransitionOnChange`, `suppressHydrationWarning` on
`<html>`. Toggle in topbar and Settings.

### 7. Mock-only, deterministic data
All data in `lib/dashboard/mock-data.ts`, deterministic (no random) to avoid
hydration mismatches and keep builds stable. Typed so a real API can replace it
without touching components.

## Guardrails encoded in the UI
- Mock-mode always visible; `Live WhatsApp/Stripe/LLM: Off`.
- Every agent action rendered behind a human approval gate.
- Phone numbers masked; no full addresses; no secrets; **no Lovable magic link
  saved in docs**.

Related: [[admin-ui-design-decisions]] · [[internal-dashboard-ui]] · [[current-build-decisions]]
