# Test Script — Partner Acquisition, Finance & Compliance, Dev & Automation

**App:** `apps/admin` · **Date:** 2026-07-21 · **Mode:** mock-only
Run `cd apps/admin && npm run build && npm run start` then open http://localhost:3000.

## Automated checks (already run — results in the build report)
- [x] `npm run typecheck` → 0 errors
- [x] `npm run lint` → clean (1 pre-existing unrelated warning)
- [x] `npm run build` → success, all 10 routes compiled
- [x] Route smoke test → all 10 sidebar routes 200; `/finance` → 307 → `/finance-compliance`
- [x] Playwright light/dark/mobile → 0 console errors & 0 horizontal overflow on new pages

## Navigation
- [ ] Sidebar shows 10 sections in order: Overview · Operations · Sales · **Partner Acquisition** · SEO Agents · Marketing · **Finance & Compliance** · **Dev & Automation** · Reports · Settings
- [ ] Old "Finance" label no longer appears; visiting `/finance` lands on `/finance-compliance`
- [ ] Active-nav highlight works for each new section (collapsed rail too)

## Partner Acquisition (`/partner-acquisition`)
- [ ] 4 role cards render (Head of Partnership, Marketing Intelligence Analyst, 2 Partner Executives) with region, pipeline, tasks, meetings, targets, status, responsibility
- [ ] 12 KPI cards render
- [ ] 6 charts render above the tabs + tab-local charts render
- [ ] 7 tabs switch: Partner Pipeline · Market Intelligence · Outreach Tracker · Meetings & Follow-ups · Compliance Queue · Regional Coverage · Partner Performance Preview
- [ ] Pipeline table shows all columns incl. Score & Compliance Status; local filters (Region/Type/Owner/Stage) narrow rows and Clear resets
- [ ] Sample partners present (Dubai Marina Laundry Hub, Al Quoz, Doha West Bay, Riyadh Corporate, London Hospitality, Toronto Condo)
- [ ] Compliance queue is status-only (no document contents / bank / license numbers)

## Finance & Compliance (`/finance-compliance`)
- [ ] Financial KPIs (incl. Driver Cost) + Compliance KPIs both render
- [ ] Global filter bar narrows financial charts (e.g. Market = UAE)
- [ ] 9 tabs switch: Financial Overview · Cost Breakdown · Customer Payments · Refunds & Adjustments · Partner/Facility Compliance · Driver Compliance · Documents & Expiry · Audit Trail · Risk Flags
- [ ] Refunds show "Approval Required" and Approve/Reject are visual only (no money moves)
- [ ] No card numbers, bank details or full customer PII anywhere

## Dev & Automation (`/dev-automation`)
- [ ] 14 KPI cards render (Total/Live/Mock agents, Failed Jobs, Latency, Uptime, LLM Calls/Cost, etc.)
- [ ] Agent Health table lists 22 agents with Status/Mode/Success/Latency/Cost/Issues/Owner; local filters work
- [ ] 9 tabs switch: Automation Overview · Agent Health · Technical Issues · API & Webhook Health · Job Queue · LLM / Cost Usage · Deployments · Integration Status · Logs & Audit
- [ ] Technical issues include the known gaps (WhatsApp conv list endpoint, approval persistence, classifier not built, etc.)
- [ ] Logs/API panels show safe summaries only — no secrets, keys, tokens or raw env values

## Reports & Settings
- [ ] Reports page shows 3 new cards: Partner Acquisition Report · Finance & Compliance Report · Dev & Automation Report
- [ ] Settings still loads; Connected apps includes Meta WhatsApp, PostgreSQL, Redis, Cloudflare R2, Cloudflare Workers, Monitoring/Logging, LLM Gateway

## Regression (existing sections must still work)
- [ ] Overview, Operations (all 4 tabs), Sales, SEO Agents, Marketing all load with no new errors
- [ ] Mock-mode banner/footer still visible

## Cross-cutting UI
- [ ] Dark mode: toggle in Settings → all three new pages recolor correctly (cards, tables, charts, chips)
- [ ] Mobile (≤ 390px): tables collapse to cards; no horizontal page scroll
- [ ] No console errors on the three new pages (browser devtools)
