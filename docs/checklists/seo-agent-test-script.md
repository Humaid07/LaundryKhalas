# SEO Agent — Test Script / Verification Checklist (Phase 1)

## Backend (from `apps/whatsapp-agent`, venv active)
```
.venv/Scripts/python.exe -m pytest tests/test_seo_agents.py -q      # 12 pass
.venv/Scripts/python.exe -m pytest -q                                # full suite, 220 pass
.venv/Scripts/python.exe -m ruff check seo_agents/ api/seo_agents.py # clean
```

## API smoke (backend running, e.g. :8101)
```
curl -s localhost:8101/api/seo/agents        | ...   # 16 agents
curl -s localhost:8101/api/seo/agent-health           # 16 rows
curl -s localhost:8101/api/seo/overview               # total_agents=16, pending_approvals>0
curl -s "localhost:8101/api/seo/tasks?status=pending"  # approval queue
curl -s localhost:8101/api/seo/reports/daily          # daily report
curl -s localhost:8101/api/seo/reports/weekly         # weekly report
curl -s -X POST localhost:8101/api/seo/agents/SEO-08/run   # on-demand run
```

## Frontend (from `apps/admin`)
```
npm run typecheck        # clean
npm run dev              # then open the routes below
```
Routes to eyeball: `/seo-agents`, `/seo-agents/agent-fleet` (should show 16 live
agents), `/seo-agents/overview`, `/seo-agents/gsc-performance`, `/seo-agents/indexing`,
`/seo-agents/content-pipeline`, `/seo-agents/hyperlocal-pages`, `/seo-agents/technical-seo`,
`/seo-agents/competitors`, `/seo-agents/ai-search`, `/seo-agents/reports`,
`/dev-automation/agent-health`, `/reports/seo`.

## Acceptance checks
- [ ] All 16 agents returned by `/api/seo/agents` and shown in Agent Fleet.
- [ ] Every agent has `dashboard_sections` (no invisible agents).
- [ ] Runs create findings + recommendations; approval-required recs create tasks.
- [ ] `/api/seo/tasks` types are within the 10 allowed approval task types.
- [ ] Approve/reject change status only — no publish/submit/outreach happens.
- [ ] SEO-16 creates no approval tasks (reporting only).
- [ ] Daily & weekly reports roll up all 16 runs (urgent first).
- [ ] Findings carry market/city/service (or scope=global) so global filters apply.
- [ ] No secrets/API keys/DATABASE_URL in code, logs, or dashboard.
- [ ] `apps/whatsapp-agent/.env` unchanged; no live external calls.

## Safety (must all be FALSE / absent)
- [ ] auto-publish blog · auto-update pages · auto-submit GSC URL · auto-send outreach
      · auto-buy backlinks · invented reviews/stats/rankings/prices.
