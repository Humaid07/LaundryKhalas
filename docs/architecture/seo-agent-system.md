# SEO Agent System — Architecture (Phase 1)

Mock-first, approval-gated SEO agent system living inside the active FastAPI
backend (`apps/whatsapp-agent`). Fully isolated from the WhatsApp/Evolution work.

## Core rule
SEO agents **research, monitor, draft, and recommend**. Humans approve publishing,
sending, outreach, backlinks, paid placements, page changes, and canonical facts.
No auto-publishing, no auto-sending, no invented stats/reviews/rankings/prices.

## Layout
```
apps/whatsapp-agent/seo_agents/
  catalog.py       # the 16 agents (source of truth): inputs, actions, dashboard map
  schemas.py       # DTOs: SEOAgent, SEOAgentRun, SEOFinding, SEORecommendation,
                   #       SEOApprovalTask, DashboardChangeLog, SEOReport
  mock_sources.py  # deterministic fixtures (competitor/GSC/indexing/… data)
  decisions.py     # agent -> approval task type, severity/priority/due-date
  runner.py        # run_agent(): mock producers -> findings/recs/tasks/changelog
  store.py         # in-memory store, seeded once from mock sources (no DB)
  approvals.py     # approve/reject a task (status only, never the real action)
  reports.py       # daily/weekly rollups (SEO-16 output)
apps/whatsapp-agent/api/seo_agents.py   # the FastAPI router (dashboard's only door)
```

## Data flow
```
catalog agent ──run_agent()──▶ SEOAgentRun
                              ├─ SEOFinding[]         (dashboard-visible)
                              ├─ SEORecommendation[]  (approval_required → task)
                              ├─ SEOApprovalTask[]    (approval queue)
                              └─ DashboardChangeLog   (user-visible message)
                                        │
                    store (in-memory) ──┴──▶ /api/seo/* ──▶ admin dashboard
                                                 └─ reports.py ──▶ daily/weekly report
```

The store is seeded at first access by running every agent once against a fixed
mock clock (`MOCK_NOW`), so the dashboard always has stable, filterable data.

## Isolation & safety decisions
- **No Supabase tables/migrations** — state is in-memory. This is why the SEO
  build cannot affect the live Evolution auto-reply flow or the dev/test Supabase
  schema. Trade-off: state resets on restart (acceptable for Phase 1 mock).
- **No live calls** anywhere — every runner reads `mock_sources.py`.
- **Every change is a task** — `runner` creates an `SEOApprovalTask` for each
  approval-required recommendation; `approvals.approve/reject` mutate status only.
- Adapter interfaces for future real sources (GSC first) are the runners
  themselves: swap a producer's data source behind an env flag in Phase 2.

## Filters
Every finding/task/run carries `market/country/city/service` + a date, and
site-wide rows set `scope="global"`, so the admin global filters
(`applyGlobalFilters`) work on SEO rows like any other section.

See also [[seo-agent-dashboard-contract]] and the build report
[[2026-07-22-seo-agent-dashboard-foundation]].
