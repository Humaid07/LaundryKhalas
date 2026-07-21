# Checklist — Internal Dashboard UI Test Script

**App:** `apps/admin` · `npm run dev` → http://localhost:3000
Run through this to verify the dashboard structure manually.

## Setup
- [ ] `cd apps/admin && npm install` (adds recharts, next-themes)
- [ ] `npm run dev` starts on port 3000
- [ ] `/` redirects to `/overview`

## Shell & navigation
- [ ] Sidebar shows all 8 sections: Overview, Operations, Sales, SEO Agents, Marketing, Finance, Reports, Settings
- [ ] Active section shows the rose active rail + rose text
- [ ] Sidebar **Collapse** shrinks to an icon rail (desktop); expands back
- [ ] **MOCK ENVIRONMENT** badge visible in sidebar footer (`Live WhatsApp · Stripe · LLM: Off`)
- [ ] Topbar: search, theme toggle, notifications (with dot), profile menu

## Filter dropdowns (custom FilterSelect)
- [ ] Filter controls are rounded pills, **not** native gray `<select>` boxes (check on Sales / Finance & Compliance / Partner Acquisition / Dev & Automation)
- [ ] Clicking a filter opens a rounded-2xl menu with soft shadow; chevron rotates up
- [ ] Selected option is rose-highlighted with a check icon; leading "All …" row clears the filter
- [ ] Escape closes; clicking outside closes; keyboard Arrow/Enter navigates
- [ ] Selecting a value updates the trigger label + shows an active rose chip; "Clear all" resets
- [ ] **Market → City dependency** still works (Market=UAE → City lists Dubai/Abu Dhabi/Sharjah)
- [ ] Focus ring is subtle **rose** (no harsh blue browser outline)
- [ ] Light + dark both polished; menu contrast strong in dark
- [ ] Mobile: pills wrap; open menu stays within viewport; **no horizontal overflow**

## Dark mode
- [ ] Sun/moon toggle flips the whole UI light ↔ dark
- [ ] Surfaces, borders, text all adapt; contrast stays readable
- [ ] **Charts recolor** for dark mode (brighter rose/plum/teal)
- [ ] Preference persists on reload (no flash of wrong theme)

## Overview
- [ ] 12 KPI cards with values, delta chips, sparklines
- [ ] Orders-over-time (stacked area), Revenue & profit (area)
- [ ] Orders by channel (donut w/ center label), Orders by city (bars), Automation rate (grouped bars)
- [ ] Latest orders table, Pending approvals, Recent WhatsApp conversations (phones masked), Tickets, Activity timeline

## Operations — four surfaces
- [ ] Top-level **segmented** switch: Customer Facing | Facility Facing | Drivers | Customer Charges / Payments (all equal top-level, none nested)
- [ ] **Customer Facing** KPIs (Open Conversations, Pending Replies, New WhatsApp Orders, …) differ from Facility KPIs
- [ ] Customer secondary tabs: WhatsApp Agent, Customer Orders, Tickets / Concerns, Order Changes, Cancellations, Follow-ups
- [ ] WhatsApp Agent tab: live console (Agent online chip, send → draft → Approve/Edit/Reject/manual takeover)
- [ ] Customer phones are masked; customer activity timeline + actions panel present
- [ ] **Facility Facing** KPIs (Awaiting Assignment, In Cleaning, Ready for Delivery, …)
- [ ] Facility secondary tabs: Facility Orders, Facility Assignment, Status Updates, Issues, Quality Checks, Delivery Handoff
- [ ] Facility Orders show **area/city only** — NO customer name/phone/email/address
- [ ] "Privacy firewall on" banner visible on Facility tab; Facility Management table shows capacity/load/PPI

### Drivers
- [ ] 10 KPIs: Active Drivers, Drivers Online, Pickups/Deliveries Assigned, Pickups/Deliveries Completed Today, Delayed Pickups/Deliveries, Avg Pickup/Delivery Time
- [ ] Secondary tabs: Driver Overview, Pickup Queue, Delivery Queue, Driver Performance, Driver Issues
- [ ] Driver Overview: name, status (Online/Busy/Offline…), zone, assigned, done today, delayed, rating/PPI, last active, actions
- [ ] Pickup & Delivery queues show customer **area/city only** — NO full name/phone/address; unassigned rows badged; "Privacy firewall on" card present
- [ ] Delivery Queue shows payment status per order; Driver Issues list issue type/priority/status/action needed

### Customer Charges / Payments
- [ ] 10 KPIs: Total Customer Charges, Paid Orders, Pending/Failed Payments, Refund Requests, Adjustments Pending, Cash/PoD, Card/Online, Invoice Payments, Payment Issues Open
- [ ] Secondary tabs: Payment Overview, Pending Payments, Refund Requests, Adjustments / Extra Charges, Payment Issues, Invoices / B2B
- [ ] Payment Overview: LK-AE-1024 (145/PoD/Pending), 1025 (90/Card/Failed), 1026 (2800/Invoice), 1027 (60/Card/Paid), 2031 (120/PoD/Pending)
- [ ] Refund Requests + Adjustments show **human approval required**; buttons labelled **mock-only**
- [ ] **No** card number / CVV / bank details / unmasked phone anywhere; method shown as label only
- [ ] Info cards present: "Operational payment view — Finance holds financial summaries" and "Mock-only · Stripe off"

- [ ] All four surfaces work in light + dark; tables scroll/convert to cards on mobile; no horizontal overflow

## Sales / SEO / Marketing / Finance / Reports / Settings
- [ ] Sales: KPIs + charts + top cities/services/customers
- [ ] SEO Agents: daily brief, KPIs, charts, 14 agent cards, task table (approval badges)
- [ ] Marketing: 8 tabs; **AI Creative Studio** → "Generate preview" shows mock creative; approval queue has Approve/Reject/Request changes/Schedule
- [ ] Finance: KPIs, revenue-vs-cost, profit trend, cost donut + breakdown table
- [ ] Reports: report cards + structured viewer
- [ ] Settings: profile, team, roles, markets, notifications + agent-guardrail switches, connected apps (status badges), theme toggle, mock-mode banner

## Responsive
- [ ] Tablet width: grids drop to 2 columns; sidebar collapsible
- [ ] Mobile width: hamburger opens drawer (overlay, Escape closes, body scroll locks)
- [ ] Mobile: **tables become cards**; no horizontal page overflow
- [ ] Tab strips scroll horizontally on mobile

## Integrity
- [ ] No console errors on any page (verified: 0 across all 8, light/dark/mobile)
- [ ] No live network calls to WhatsApp/Stripe/LLM/social/SEO providers
- [ ] No secrets or magic links anywhere in the UI or docs

## Automated verification (this session)
- typecheck `tsc --noEmit`: **PASS**
- `npm run build`: **PASS** (18 routes; 8 dashboard routes static)
- Playwright sweep (8 pages × light/dark/mobile): **0 console errors**, charts render + recolor

## Automated verification (2026-07-21 — Drivers + Payments)
- `tsc --noEmit`: **PASS** (0 errors)
- `next build`: **PASS** (`/operations` 23.9 kB; only pre-existing `conversations` useMemo warning)
- `next lint`: **PASS** (no errors in new files)
- Playwright `/operations`: Drivers + Payments render light & dark; mobile 390px → no horizontal overflow; only console noise is `ERR_CONNECTION_REFUSED` from the (offline) WhatsApp-agent API, unrelated to these UI sections

## Automated verification (2026-07-21 — FilterSelect dropdown redesign)
- `tsc --noEmit`: **PASS** (0 errors)
- `next build`: **Compiled successfully** + type-check clean + 24/24 static pages generated; command then exits non-zero on a Windows-only `.next/export/500.html` rename race (Defender file-lock) — unrelated to this React-only change, reproduced twice
- Playwright `/sales`: menu open/close, select updates value, **Market→City dependency** (All/Dubai/Abu Dhabi/Sharjah), chips, Escape, outside-click, Clear all — all ✅; light + dark polished; mobile 390px → `scrollWidth==clientWidth` (no overflow); **0 console errors**

## Operations subsection pages (2026-07-21)
Manual:
- [ ] `/operations` is a clean **landing** with 4 cards (Customer Facing, Facility Facing, Drivers, Customer Orders) — each with description, 3-KPI summary, status badge, "Open section"
- [ ] Cards navigate to `/operations/customer-facing|facility-facing|drivers|customer-orders`
- [ ] Breadcrumb + pill sub-nav appear on each subsection and switch cleanly; sidebar keeps **Operations** highlighted
- [ ] Customer Facing: **WhatsApp Agent console still works** (first tab); Conversations tab has no phone column; Refund Requests KPI present
- [ ] Facility Facing: **Privacy firewall banner present**; tables show area/city only
- [ ] Drivers: overview + pickup/delivery queues render; area/city only
- [ ] Customer Orders: All/Active/Completed/Cancelled/Issues/Changes tabs; global filter bar **+ local Order Status & Payment Status** filters work
- [ ] Payments no longer a top-level Operations subsection
- [ ] Dark mode + mobile (390px): no horizontal overflow anywhere

Automated:
- `tsc --noEmit`: **PASS** (0 errors); `next lint`: clean (pre-existing unrelated warning)
- Build: worked around the Windows shared-`.next` collision by building to an **isolated `distDir`** (`LK_DIST_DIR=.next-verify`) → **exit 0, 24/24 static pages**
- Playwright (light + dark @1280; mobile @390) on all 5 Operations routes: **0 console errors, 0 React #425 hydration errors, 0 horizontal overflow**; landmarks verified (4 landing cards, WhatsApp Agent tab, Facility privacy banner, mobile table→cards)
- `formatRelativeTime` made deterministic (`MOCK_NOW`) → eliminated the repo-wide hydration text mismatch on statically-prerendered pages
- Confirmed the live dev server (`:3005`) recovered to healthy CSS after verification

## Global filters across ALL sections (2026-07-21)
See `docs/architecture/dashboard-filter-system.md` and
`docs/build-reports/2026-07-21-global-filters-all-sections.md`.

Manual — set **UAE → Dubai → Dry Cleaning** in the global bar, then check:
- [ ] Filter chips show the active selection; **Clear all** resets everything
- [ ] Region → Market → City dependency: picking Region=GCC limits Market options;
      Market=UAE limits City to Dubai/Abu Dhabi/Sharjah; changing a coarser level
      resets an incompatible finer selection
- [ ] Filters **persist** when navigating between sections and into subsections
      (client-side nav; a hard reload resets them by design)
- [ ] **Overview** — Latest orders + WhatsApp conversations narrow; by-channel /
      by-city charts narrow; KPI grid shows the **"Overall snapshot"** badge
- [ ] **Operations / Customer Orders** — All/Active/Completed/Cancelled/**Issues**
      narrow to Dubai; KPI snapshot badge
- [ ] **Operations / Drivers** — overview, pickup/delivery queues, **performance
      and issues** narrow to Dubai; KPI snapshot badge
- [ ] **Operations / Facility Facing** — orders/QC/handoff/**issues** narrow
- [ ] **Operations / Payments** — overview/pending/refunds/adjustments/issues and
      **B2B invoices** narrow (invoices carry city + channel)
- [ ] **Sales / Services** + **B2B/B2C** — service chart narrows; **business
      accounts** table narrows with a filter-aware empty state; aggregates badged
- [ ] **Partner Acquisition / Pipeline** + **Market Intelligence** — tables
      narrow; market-readiness & outreach-conversion charts recompute; rollup
      KPIs/donuts badged
- [ ] **Marketing / Campaigns** — campaigns/social/PR/UGC narrow; overview /
      analytics / calendar / approvals / UTM show the **"Brand-wide"** badge
- [ ] **Finance & Compliance / Customer Payments** + **Cost Breakdown** — payment
      & compliance tables narrow; cost breakdown + KPI rollups badged; **no card /
      CVV / bank / full-address fields** anywhere
- [ ] **Dev & Automation / Agent Health** (local filters) + geo-tagged technical
      rows; overview / LLM / deployments show **"Global / technical"**; no section
      looks broken/empty under a geo filter
- [ ] **SEO / Content Pipeline** — geo-tagged pages/tasks narrow; site-wide items
      stay visible ("Global / site-wide")
- [ ] **Reports** — each report shows the active-filter **scope** in its header
- [ ] **Settings** — NOT filtered (no global bar / no geo scoping)
- [ ] A non-matching combination (e.g. City = Muscat on a Dubai-only table) shows
      **"No records match the selected filters"** + a Clear-filters button
- [ ] Dark mode + mobile (390px): badges/empty states render; no console errors

Automated:
- `tsc --noEmit`: **PASS** (0 errors)
- `tsx lib/dashboard/filters.test.ts`: **PASS** (45 assertions)
- Route smoke on `next dev`: all changed routes → **HTTP 200**
- Playwright (headless): City=Dubai on Drivers → snapshot badge shown, Driver
  Issues table drops Doha (LK-24808) keeps Dubai (LK-24814); client-side nav to
  Customer Orders → **chip persists**, All Orders drops Doha (LK-24815) keeps
  Dubai (LK-24817); **0 console/page errors**
