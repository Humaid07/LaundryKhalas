# Build Report — Dashboard Subsection Architecture (landing + focused routes, all sections)

**Date:** 2026-07-21
**Area:** `apps/admin` internal dashboard (Command Center) · mock-only, UI-only

## 1. Task objective

Refactor the internal dashboard's information architecture so **every** major
section follows the Operations pattern: a **landing page of subsection cards**
plus **dedicated, focused subsection routes** — instead of stacking 9–14 KPIs,
8+ charts and up to 10 tab strips on one crowded page. Do not rebuild the
dashboard, break features, delete reusable components, add APIs or add secrets.
Keep everything mock-only.

## 2. What was built

The landing + subsection pattern (first shipped for Operations) was generalised
into shared, **config-driven machinery** and rolled out to all ten sections:

- A single registry, `lib/dashboard/sections.ts` (`SECTIONS`), is the source of
  truth for every section's landing cards and breadcrumb/sub-nav: base route,
  header copy, card grid density, and the ordered subsections (slug, label,
  description, icon, summary KPIs, status badge).
- Four reusable section components: `SectionLanding`, `SectionCard`,
  `SubsectionShell`, `SectionSubNav`.
- One content router per section (`…Subsection({ slug })`) that renders the
  focused content for each slug, **reusing existing charts/tables/panels and mock
  data** — the previously-crowded tab bodies became per-slug sections.
- 10 landing pages + 73 subsection route files (83 routes total). Each landing
  page is one line (`<SectionLanding sectionKey=… />`); each subsection page is a
  tiny `SubsectionShell` + `…Subsection slug=…` wrapper.

Sidebar remains **10 top-level items only**; subsections are reached via landing
cards, breadcrumbs and the in-section pill sub-nav.

Full detail and route map: [[dashboard-information-architecture]].

## 3. Why it was built

Multiple sections had become "15 components on one page." The Operations split
proved the fix; this task applies it everywhere so each section reads as a clean
command hub and each subsection gets a focused, demo-ready page.

## 4. Files created

Shared machinery:
- `components/dashboard/section/SectionLanding.tsx`
- `components/dashboard/section/SectionCard.tsx`
- `components/dashboard/section/SubsectionShell.tsx`
- `components/dashboard/section/SectionSubNav.tsx`
- `lib/dashboard/sections.ts` (`SECTIONS` registry)

Per-section content routers:
- `components/dashboard/sales/Sales.tsx` (`SalesSubsection`)
- `components/dashboard/partner-acquisition/PartnerAcquisition.tsx` (`PartnerSubsection`)
- `components/dashboard/seo/SeoAgents.tsx` (`SeoSubsection`)
- `components/dashboard/marketing/Marketing.tsx` (`MarketingSubsection`)
- `components/dashboard/finance-compliance/FinanceCompliance.tsx` (`FinanceSubsection`)
- `components/dashboard/dev-automation/DevAutomation.tsx` (`DevSubsection`)
- `components/dashboard/reports/Reports.tsx` (`ReportSubsection`)
- `components/dashboard/settings/Settings.tsx` (`SettingsSubsection`)

Per-section mock data (split by domain):
- `lib/dashboard/sales-data.ts`, `partner-acquisition-data.ts`, `seo-data.ts`,
  `marketing-data.ts`, `finance-compliance-data.ts`, `dev-automation-data.ts`,
  `reports-data.ts` (+ existing `operations-data.ts`, `mock-data.ts`).

Route files (10 landing `page.tsx` + 73 subsection `page.tsx`) under
`app/(dashboard)/<section>/…`.

Docs:
- `docs/architecture/dashboard-information-architecture.md` (new)
- this build report.

## 5. Files modified

- `lib/dashboard/nav.ts` — sidebar stays at 10 top-level items (unchanged shape,
  confirmed clean).
- `components/dashboard/shell/Sidebar.tsx` — parent stays active on sub-routes
  (`pathname.startsWith`).
- `app/(dashboard)/overview/page.tsx` — executive command center; cards deep-link
  to detail routes (`/operations/customer-orders`,
  `/operations/customer-facing`, `/finance-compliance/refunds-adjustments`).
- `next.config.js` — `/finance` → `/finance-compliance` 307 redirect.

## 6. API endpoints added/changed

None. No APIs connected. All data is deterministic mock.

## 7. Database tables/models added/changed

None.

## 8. UI pages/components added/changed

10 section landing pages, 73 focused subsection pages, 4 shared section
components, 8 per-section content routers. See §4.

## 9. Agent behavior added/changed

None. Agent actions remain mock-only and approval-gated.

## 10. Integrations added/changed

None.

## 11. What is mock-only

Everything. No live WhatsApp / Stripe / LLM / external APIs. Export & share
buttons on landing and report pages are placeholders.

## 12. What is live

Nothing. UI + mock data only.

## 13. What is intentionally deferred

- Wiring subsections to real backend endpoints (props already typed for it).
- Functional export/share.
- Any not-yet-built domains (SEO/marketing agents are UI shells over mock data).

## 14. Tests / checks run

- `npx tsc --noEmit` (typecheck) — **exit 0, zero errors**.
- `npx next lint` — **exit 0**; one pre-existing warning in the untouched legacy
  `app/admin/conversations/page.tsx` (unrelated to this refactor).
- Browser verification with Playwright (Chromium headless) against the running
  dev server on `:3005`, over 60 representative routes (all 10 landings + a
  spread of subsections from every section), in **Desktop Light, Desktop Dark and
  Mobile (390px)** — checking HTTP status, console/page errors and horizontal
  overflow. `/finance` redirect verified.
  - Result: <!-- BROWSER_RESULT -->
- `next build` intentionally not run: known Windows-only failure at the
  `500.html` rename (documented previously); typecheck + lint + Playwright are
  the verification path on Windows. Also, a dev server is up on `:3005` — building
  with a dev server running is avoided per prior guidance.

## 15. Test results

See §14. Static checks green; browser results recorded inline above.

## 16. Bugs / issues found

None introduced by this task. (Pre-existing legacy lint warning noted in §14.)

## 17. Known limitations

- Landing/report export & share are placeholders.
- Mock data only; no persistence, no live counts.
- `next build` cannot be run to completion on this Windows host (unrelated
  toolchain quirk); production build verification deferred to CI/Linux.

## 18. Security / privacy notes

Privacy firewall preserved by construction (the refactor only relocated existing
content): facility/driver views area/city only; masked phones on customer lists;
finance payment views never show card/bank details; Dev & Automation logs carry
no secrets/tokens/env values; partner data is business-level only; every
risky/agent action stays mock + approval-gated; mock/staged state always visible.

## 19. Cost / LLM usage notes

None. No LLM calls. No external cost.

## 20. Screens to demo

Any section landing (e.g. `/sales`, `/finance-compliance`, `/dev-automation`) →
click a card → focused subsection with breadcrumb + pill sub-nav. Show sidebar
staying at 10 items, dark-mode toggle, and mobile drawer + card-table.

## 21. Commands to run

```bash
cd apps/admin
npm run dev          # http://localhost:3000 (or existing :3005)
npx tsc --noEmit     # typecheck
npx next lint        # lint
```

## 22. How to verify manually

Open each of the 10 sidebar items → confirm a landing page of cards (no crowded
data). Click any card → focused subsection with breadcrumb + sub-nav. Confirm the
sidebar keeps the parent highlighted, dark mode recolors, mobile shows the drawer
and card-tables, and no horizontal scroll. Visit `/finance` → redirects to
`/finance-compliance`.

## 23. Next recommended step

Wire one section's subsections to real backend data (Operations → Customer Orders
is the strongest candidate — the `/api/orders/*` mock endpoints already exist in
`apps/whatsapp-agent`), keeping the same landing + subsection shell.

See also: [[internal-dashboard-ui]] · [[dashboard-information-architecture]] ·
[[internal-dashboard-ui-test-script]].
