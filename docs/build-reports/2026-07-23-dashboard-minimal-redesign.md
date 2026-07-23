# Build Report — Dashboard Minimal Redesign

**Date:** 2026-07-23
**Branch:** orders-vertical-slice
**Related:** [[minimal-dashboard-design-system]]

## 1. Task objective
Redesign the entire command-center dashboard to be **minimal, clean, spacious, and easy to understand**, using Linear / Stripe Dashboard / Vercel-shadcn as design inspiration. Reduce information on main pages; move full detail and all actions into click-through detail pages (progressive disclosure). Apply across **all** sections.

## 2. What was built
- A shared **minimal component library** (`components/dashboard/minimal/`) that all sections import from.
- A redesign of **every dashboard section**'s main pages to a calm, low-density layout: compact KPI strip → workflow/status tabs → a scannable list/table of light record previews (2–3 fields, one badge, no actions).
- **12 new full detail-page routes** carrying the heavy information + all actions, replacing cramped 480px side drawers as the primary detail surface.

## 3. Why it was built
Main pages were overwhelming — dense multi-field cards, many badges, and drawers as the primary detail experience. The redesign enforces one rule: **Overview stays rich; every other main page is minimal**, with full data one click away.

## 4. Design inspiration used
- **Linear** — sidebar, spacing, calm hierarchy, muted inactive states, progressive disclosure.
- **Stripe Dashboard** — professional detail pages, clean tables, grouped info, subtle status/action patterns.
- **Vercel / shadcn** — minimal cards, clean typography, modern admin structure.
Used as inspiration only; the LaundryKhalas rose-white / deep-slate identity is preserved.

## 5. UX rules introduced
1. Overview can be rich; all other main pages are minimal.
2. Progressive disclosure: main page = light summary → card/row = short preview → detail page = full data → actions only on detail pages.
3. Cards: **2–3 fields max, one status badge**, no long descriptions.
4. More spacing (`space-y-6`, `gap-6`), fewer colors, subtle borders (`border-border/70`), muted secondary text.
5. Full detail pages preferred over side drawers for important records.
6. Actions (incl. approval-gated, RULE 13) live only on detail pages.

## 6. Files created
**Shared library — `apps/admin/components/dashboard/minimal/`:**
- `MinimalPageHeader.tsx`, `MinimalKpiStrip.tsx`, `CompactRecordCard.tsx` (+ `RecordList`), `DataPreviewTable.tsx`, `DetailPageShell.tsx` (+ `DetailColumns`), `DetailSectionCard.tsx` (+ `Field`, `FieldGrid`, `Chip`), `ActionMenu.tsx`, `ViewDetailsButton.tsx`, `index.ts` (barrel; re-exports `WorkflowTabs`, `StatusBadge`, `EmptyState`, states).

**Operations detail pages + routes:**
- `operations/facility-detail/{data.ts, FacilityOrderDetailPage.tsx}` + `app/(dashboard)/operations/facility-facing/orders/[orderId]/page.tsx`
- `operations/driver-detail/{data.ts, DriverDetailPage.tsx}` + `app/(dashboard)/operations/drivers/[driverId]/page.tsx`
- `operations/support-detail/{data.ts, TicketDetailPage.tsx}` + `app/(dashboard)/operations/customer-facing/tickets/[ticketId]/page.tsx`

**Other sections' detail pages + routes:**
- SEO: `seo/agent-detail/AgentDetailPage.tsx` + `app/(dashboard)/seo-agents/agents/[agentId]/page.tsx`
- Marketing: `marketing/campaign-detail/…` + `marketing/approval-detail/…` + routes `marketing/campaigns/[campaignId]`, `marketing/approvals/[approvalId]`
- Partner Acquisition: `partner-acquisition/lead-detail/…` + route `partner-acquisition/pipeline/[leadId]`
- Finance & Compliance: `finance-compliance/payment-detail/…` + `finance-compliance/refund-detail/…` + routes `finance-compliance/customer-payments/[orderId]`, `finance-compliance/refunds-adjustments/[refundId]`
- Dev & Automation: `dev-automation/job-detail/…` + `dev-automation/agent-detail/…` + routes `dev-automation/job-queue/[jobId]`, `dev-automation/agent-health/[agentId]`
- Reports: `reports/report-detail/ReportDetailPage.tsx` + route `reports/view/[reportId]`

**Docs:** `docs/architecture/minimal-dashboard-design-system.md`, this build report.

## 7. Files modified
- Operations main pages: `operations/CustomerOrders.tsx`, `FacilityFacing.tsx`, `Drivers.tsx`, `CustomerFacing.tsx` (minimal rewrite, drawers removed).
- `app/(dashboard)/operations/customer-facing/page.tsx` (wrapped `CustomerFacing` in `<Suspense>` for `useSearchParams`).
- Section routers (full minimal rewrite): `seo/SeoAgents.tsx`, `marketing/Marketing.tsx`, `partner-acquisition/PartnerAcquisition.tsx`, `finance-compliance/FinanceCompliance.tsx`, `dev-automation/DevAutomation.tsx`, `reports/Reports.tsx`.
- Data files (pure getters/slug helpers added; **no existing exported shapes changed**): `seo-data.ts`, `marketing-data.ts`, `partner-acquisition-data.ts`, `finance-compliance-data.ts`, `dev-automation-data.ts`, `reports-data.ts`.

## 8. API endpoints added/changed
None. Backend API structure and live clients untouched.

## 9. Database tables/models added/changed
None.

## 10. UI pages/components added/changed
- **11 reusable minimal components** created (list in §6).
- **All main pages** across Operations, SEO Agents, Marketing, Partner Acquisition, Finance & Compliance, Dev & Automation, Reports made minimal.
- **12 new detail-page routes** added (Operations ×3, SEO ×1, Marketing ×2, Partner ×1, Finance ×2, Dev ×2, Reports ×1).

## 11. Agent behavior added/changed
None. This is a UI/UX change only.

## 12. Integrations added/changed
None. No live WhatsApp / Stripe / LLM calls. Live API clients (`seo-agent-api`, `whatsapp-*`) untouched.

## 13. Before vs after behavior
- **Before:** dense main pages — up to 8 fields per card, multiple badges, full KPI grids with sparklines, and 480px side drawers as the primary detail surface (inconsistent: Customer Orders already had a full page, the other three Operations subsections used drawers).
- **After:** every main page is a compact KPI strip + workflow tabs + a spacious list of light cards (≤3 fields, one badge, chevron). Clicking any record opens a dedicated full detail page (Stripe-style two-column: fields/lifecycle in main, snapshots + `ActionMenu` in sidebar). Drawers removed as the primary detail experience.

## 14. What is mock-only
Everything on these pages. All record data is deterministic mock data; every action (status change, assign, approve, refund, retry, export) is inert in mock mode. Approval-gated actions are labelled but perform no live effect.

## 15. What is live
Nothing new. Existing live behaviour (behind flags) is unchanged and still gated.

## 16. What is intentionally deferred
- Wiring detail-page actions to real mutations (still mock).
- Cancellation/follow-up records in Customer Facing route to the related order/inbox rather than getting their own dedicated detail routes (kept scope bounded; can add later).
- Drivers/Facility main pages don't restore the `?tab=` on back-nav (they default to the first tab); Customer Facing and Customer Orders do restore it.

## 17. Tests run
- `npx tsc --noEmit` (full project) after all changes.
- Playwright (headless Chromium) render + console-error checks on representative pages of every section and detail routes, via a running `next dev` server (Windows `next build` is known to fail at the 500.html rename — verification is via tsc + dev + Playwright per repo convention).

## 18. Test results
- **TypeScript: 0 errors project-wide.**
- **Rendering: 0 page/console errors** on Operations (4 main + facility/driver detail), SEO (Agent Fleet), Finance (Customer Payments), Partner (Pipeline), Dev (Job Queue), Reports (Operations Report), Marketing (Campaigns). Detail routes return HTTP 200; not-found fallbacks render correctly for unknown ids.
- The only console line observed is `ERR_CONNECTION_REFUSED` from the optional live agent backend (:8100) not running — expected; the live panels fall back gracefully.

## 19. Bugs/issues found (and fixed)
- `CompactRecordCard` referenced `interactive` before declaration (TDZ) — fixed by hoisting.
- `useSearchParams()` added to `CustomerFacing` without a Suspense boundary — fixed by wrapping in `<Suspense>` (would otherwise break prerender).
- `priorityTone` imported from the wrong module in `DriverDetailPage` — fixed (it lives in `status-maps`).

## 20. Known limitations
- Actions are mock-only (no live effects).
- Some secondary record types reuse a related detail route instead of a bespoke one (see §16).
- Concurrent `tsc` runs can share `.tsbuildinfo` and momentarily report stale counts; the final single run is authoritative (0).

## 21. Security/privacy notes
- Privacy firewall preserved: facility/driver views show **area/city only**; Customer Facing masks phones; Finance shows amount/method/status/area only — **no card numbers, CVV, bank details, or unmasked phone** anywhere.
- Approval-gated actions (cancellations, refunds, adjustments, campaign go-live, job retry/redeploy) are labelled `approval: true` and inert in mock mode (RULE 13).
- No secrets or env values added or exposed.

## 22. Cost/LLM usage notes
No LLM calls at runtime. The redesign is static UI. (Build-time only: this task used background subagents to parallelize the six section rewrites.)

## 23. Screens/pages to demo
- Operations → Customer Orders (minimal list) → open an order (full detail page).
- Operations → Facility Facing → open a facility order (`/orders/[orderId]`) — Stripe-style two-column detail.
- Operations → Drivers → open a driver (`/drivers/[driverId]`) with aggregated tasks.
- Finance & Compliance → Customer Payments (calm list + privacy note) → payment detail.
- Marketing → Campaigns → campaign detail with `ActionMenu`.
- SEO Agents → Agent Fleet → agent detail.

## 24. Commands to run
```
cd apps/admin
npm run typecheck          # tsc --noEmit → 0 errors
npx next dev -p 3021       # then visit http://localhost:3021/operations/customer-orders
```
(Do not run `next build` with a dev server up on Windows.)

## 25. How to verify manually
Open any main page: confirm a compact KPI strip, workflow tabs, and a spacious list of light cards (≤3 fields, one badge, a chevron). Click a card → a full detail page opens with grouped sections and a "More actions" menu; "back" returns to the list. Confirm no side drawer opens for these records. Toggle dark mode — surfaces stay calm and readable.

## Next recommended step
Wire the detail-page `ActionMenu` items to real (still-gated) mutations for the approval workflow, and add the remaining bespoke detail routes for secondary record types (cancellations, follow-ups) if operators want them.
