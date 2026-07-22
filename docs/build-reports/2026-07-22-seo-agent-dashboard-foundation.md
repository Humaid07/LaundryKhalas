# Build Report — SEO Agent Foundation & Dashboard Wiring

**Date:** 2026-07-22
**Commit message:** `Add SEO agent foundation and dashboard wiring`

## 1. What was built
A production-shaped, **mock-first, approval-gated** SEO Agent system inside the
active FastAPI backend (`apps/whatsapp-agent`), plus a typed dashboard API client
and live wiring of the SEO Agent Fleet. Every agent is dashboard-visible; no
backend-only invisible agents. No live web/Google/GSC/LinkedIn/Ahrefs/Semrush/
publishing calls. Nothing auto-publishes, auto-submits, or auto-sends.

Isolation: the SEO system uses an **in-memory store** (no Supabase migration), so
the live WhatsApp/Evolution work and the dev/test Supabase schema are untouched.
`apps/whatsapp-agent/.env` was not modified.

## 2. Agents modeled (16) and their dashboard mapping
| Agent | Name | Mode | Primary dashboard surfaces |
|-------|------|------|-----------------------------|
| SEO-01 | Competitor Monitor | monitor | competitors, overview, reports, agent-health |
| SEO-02 | News & Industry Trend Monitor | monitor | content-pipeline, reports, agent-health |
| SEO-03 | Google Search Console Monitor | monitor | gsc-performance, overview, reports, agent-health |
| SEO-04 | Indexing & Sitemap Agent | approval | indexing, reports, approvals, agent-health |
| SEO-05 | Content Research Agent | monitor | content-pipeline, hyperlocal-pages, reports |
| SEO-06 | Blog + Schema Draft Agent | draft | content-pipeline, reports, approvals |
| SEO-07 | Topical Authority Agent | monitor | content-pipeline, hyperlocal-pages, reports |
| SEO-08 | Internal Linking Agent | approval | technical-seo, content-pipeline, approvals |
| SEO-09 | Backlink Opportunity Agent | approval | competitors, reports, approvals |
| SEO-10 | Duplicate Content Agent | monitor | technical-seo, reports, approvals |
| SEO-11 | Money Page Optimization Agent | approval | technical-seo, hyperlocal-pages, approvals |
| SEO-12 | Local & Area Page Agent | approval | hyperlocal-pages, content-pipeline, approvals |
| SEO-13 | Content Decay & Cannibalization Agent | monitor | gsc-performance, technical-seo, reports |
| SEO-14 | AI Search Visibility Agent | monitor | ai-search, reports, approvals |
| SEO-15 | GCC Expansion SEO Agent | monitor | hyperlocal-pages, content-pipeline, reports |
| SEO-16 | SEO Reporting Agent | monitor | reports, overview, agent-health |

Full mapping + data contract: [[seo-agent-dashboard-contract]].

## 3. Files created / modified
**Created (backend):** `apps/whatsapp-agent/seo_agents/{__init__,schemas,catalog,mock_sources,decisions,runner,store,approvals,reports}.py`, `apps/whatsapp-agent/api/seo_agents.py`, `apps/whatsapp-agent/tests/test_seo_agents.py`.
**Modified (backend):** `apps/whatsapp-agent/main.py` (registered `seo_agents.router`).
**Created (frontend):** `apps/admin/lib/dashboard/seo-agent-api.ts` (typed client + mock fallback).
**Modified (frontend):** `apps/admin/components/dashboard/seo/SeoAgents.tsx` (Agent Fleet now consumes live `/api/seo/agent-health`, all 16 agents, with static fallback).
**Docs:** this report, `docs/architecture/seo-agent-system.md`, `docs/architecture/seo-agent-dashboard-contract.md`, `docs/checklists/seo-agent-test-script.md`, `docs/00-Home.md`.

## 4. API endpoints (prefix `/api/seo`)
`GET /agents`, `GET /agents/{id}`, `GET /agent-health`, `GET /runs`, `GET /runs/{id}`,
`POST /agents/{id}/run`, `GET /findings`, `GET /recommendations`, `GET /changes`,
`GET /tasks`, `POST /tasks/{id}/approve`, `POST /tasks/{id}/reject`,
`GET /reports/daily`, `GET /reports/weekly`, `GET /overview`.

## 5. Dashboard pages wired
- **Agent Fleet** (`/seo-agents/agent-fleet`): LIVE — renders all 16 agents from `/api/seo/agent-health`, graceful fallback to the static list.
- Client methods exist (same DTOs) for Overview, GSC, Indexing, Content Pipeline, Hyperlocal, Technical, Competitors, AI Search, Reports, Approvals — these subsections still render their existing `seo-data.ts` mock arrays; swapping each to the client is a mechanical next step (adapter is ready).

## 6. Mock / live status
- **Mock-only:** all agent output (deterministic fixtures in `mock_sources.py`), in-memory store, GSC data, indexing data. Resets on backend restart.
- **Live (wiring, not data):** Agent Fleet fetches real API responses; the data behind them is mock.
- **No live external integrations** of any kind.

## 7. Approval safety
Every recommendation that implies a page/content/link/schema/index/outreach change
is `approval_required` and becomes an `SEOApprovalTask` (types restricted to the 10
allowed). Approve/reject ONLY change task/recommendation status — they never
publish, edit, submit, or send. SEO-16 (reporting) raises no tasks. Global forbidden
actions are attached to every agent (no auto-publish/submit/outreach/buy/invention).

## 8. Tests run
- `pytest apps/whatsapp-agent` → **220 passed** (12 new SEO tests + no regression to WhatsApp/Evolution).
- `ruff check seo_agents/ api/seo_agents.py tests/test_seo_agents.py` → clean.
- `npm run typecheck` (admin) → clean.
- Live HTTP smoke on `:8101`: `/api/seo/{agents,agent-health,overview,tasks,reports/daily}` all 200; 16 agents, 33 pending approvals.

## 9. Known limitations
- In-memory store resets on restart (no persistence in Phase 1 — deliberate, avoids DB migration).
- Only Agent Fleet is wired to live data; other subsections still read local mock arrays (client is ready to swap them).
- Dev & Automation → Agent Health still shows its existing static SEO rows; aligning it 1:1 with the catalog (or pointing it at `/api/seo/agent-health`) is a pending mechanical step.
- Reply/content text is templated (no LLM), by design.

## 10. Recommended next step
1. Swap the remaining SEO subsections (Overview/GSC/Indexing/Content/Hyperlocal/Technical/Competitors/AI/Reports/Approvals) from mock arrays to `seoAgentApi` (DTOs already match) and point Agent Health at `/api/seo/agent-health`.
2. Then Phase 2: connect ONE read-only real source (Google Search Console) behind an env flag + approval gates; keep all publish/submit/outreach approval-only.
