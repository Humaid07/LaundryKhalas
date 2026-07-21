# Presentation Notes — Internal Dashboard Demo (Week 01)

**Date:** 2026-07-20 · Mock environment

## 1. What we can show
A complete, premium **internal Command Center** for LaundryKhalas — the shell,
navigation, dark mode, and all eight sections (Overview, Operations, Sales, SEO
Agents, Marketing, Finance, Reports, Settings) — running live on realistic mock
data across all six GCC markets.

## 2. Suggested demo flow (~5 min)
1. **Overview** — the command center: KPIs with sparklines, orders/revenue
   trends, channel/city breakdowns, latest orders, pending approvals, live
   activity. "This is the one screen to run the business from."
2. **Dark mode** — flip the toggle; the whole UI and every chart recolor.
3. **Operations → WhatsApp Agent** — conversation list + WhatsApp-style chat
   preview + a drafted reply **held for approval** (ties to the agent we built).
4. **SEO Agents** — the daily brief ("urgent first") and the 14-agent fleet with
   approval gates.
5. **Marketing → AI Creative Studio** — type a prompt, "Generate preview",
   "Send for approval". Show HeyGen/Gamma/Meta/Composio/Apollo as placeholders.
6. **Finance** — executive revenue/cost/profit view.
7. **Mobile** — shrink the window: drawer nav, tables become cards.

## 3. Screenshots needed
Overview (light + dark), Operations WhatsApp tab, Marketing Creative Studio,
SEO Agents brief, Finance, Overview on mobile. (Captured this session.)

## 4. Talking points
- **"Pink done tastefully"** — rose is a signal (brand, active, primary,
  one chart hue), not a wash. Reads premium, not toy.
- **Executive + ops friendly** — Linear-level spacing, Stripe-clean surfaces,
  Metricool-level analytics clarity, one consistent system in light and dark.
- **Safety is visible** — MOCK ENVIRONMENT badge, `Live … : Off`, and a human
  approval gate on every agent action.

## 5. Simple technical explanation
"It's the real dashboard shell built on mock data. Every page, chart and table
is there and responsive. Nothing is connected to live WhatsApp, payments or AI
yet — we plug those in one by one behind this structure."

## 6. Business value
One command center for the whole operation and every future agent; a
demo-ready, presentation-ready surface for weekly updates; a foundation the team
can extend feature-by-feature without redesigning.

## 7. Before vs after
- **Before:** a narrow legacy WhatsApp-ops admin (indigo) + a standalone chat UI.
- **After:** a unified, premium rose/white command center with 8 sections, dark
  mode, full responsiveness, and a reusable component library.

## 8. Risks / caveats to mention honestly
- Everything is **mock** — filters/search are presentational, buttons don't
  persist, no detail pages yet, WhatsApp Agent not yet wired in.
- No live integrations; Next.js version should be bumped before any deploy.

## 9. What's coming next
Wire the existing WhatsApp Agent (:8100) into Operations; make global filters
re-slice data; then build out each section's real workflows on top of this shell.

Related: [[internal-dashboard-ui]] · [[ADR-internal-dashboard-design-system]] ·
[[week-01-standalone-whatsapp-agent-demo]]
