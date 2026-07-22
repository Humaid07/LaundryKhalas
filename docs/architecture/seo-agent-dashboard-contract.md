# SEO Agent → Dashboard Contract

Guarantees every SEO agent leaves **visible evidence** in the dashboard: status,
run history, findings, recommendations, approval tasks, and report impact. No
backend-only invisible agents.

## Agent → dashboard mapping
Each agent's `dashboard_sections` (in `catalog.py`) drives where its output shows.
Routes are under `/seo-agents/*` plus `agent-health`, `approvals`, `reports`.

| Agent | Dashboard surfaces |
|-------|--------------------|
| SEO-01 Competitor Monitor | competitors, overview, reports, agent-health |
| SEO-02 News & Trend Monitor | content-pipeline, reports, agent-health |
| SEO-03 GSC Monitor | gsc-performance, overview, reports, agent-health |
| SEO-04 Indexing & Sitemap | indexing, reports, approvals, agent-health |
| SEO-05 Content Research | content-pipeline, hyperlocal-pages, reports |
| SEO-06 Blog + Schema Draft | content-pipeline, reports, approvals |
| SEO-07 Topical Authority | content-pipeline, hyperlocal-pages, reports |
| SEO-08 Internal Linking | technical-seo, content-pipeline, approvals |
| SEO-09 Backlink Opportunity | competitors, reports, approvals |
| SEO-10 Duplicate Content | technical-seo, reports, approvals |
| SEO-11 Money Page Optimization | technical-seo, hyperlocal-pages, approvals |
| SEO-12 Local & Area Page | hyperlocal-pages, content-pipeline, approvals |
| SEO-13 Content Decay & Cannibalization | gsc-performance, technical-seo, reports |
| SEO-14 AI Search Visibility | ai-search, reports, approvals |
| SEO-15 GCC Expansion | hyperlocal-pages, content-pipeline, reports |
| SEO-16 SEO Reporting | reports, overview, agent-health |

## Data contract (DTOs served by `/api/seo/*`)
- **SEOAgentRun** — run_id, agent_id/name, status, started/completed_at, market,
  country, city, service, summary, findings_count, recommendations_count,
  urgent_count, approval_tasks_created, dashboard_sections_affected, next_action, mode.
- **SEOFinding** — finding_id, run_id, agent_id, finding_type, title, description,
  page_url, competitor_url, market/country/city/service, priority, severity,
  impact_reason, recommended_action, dashboard_section, scope, created_at.
- **SEORecommendation** — recommendation_id, run_id, agent_id, title,
  recommendation_type, page_url, suggested_change, expected_impact,
  approval_required, approval_status, assigned_to, dashboard_section, created_at.
- **SEOApprovalTask** — task_id, agent_id, run_id, task_type, title, description,
  page_url, market/city/service, priority, approval_status, suggested_action,
  assigned_to, created_at, due_date.
- **DashboardChangeLog** — change_id, agent_id, run_id, dashboard_section,
  change_type, before_summary, after_summary, priority, user_visible_message, created_at.

## Approval task types (only these 10)
`content_update, blog_draft, internal_link_change, schema_update,
indexing_resubmission, backlink_outreach, duplicate_merge,
money_page_optimization, area_page_update, ai_visibility_update`.

## Frontend adapter
`apps/admin/lib/dashboard/seo-agent-api.ts` (`seoAgentApi`) exposes: `listSeoAgents,
getSeoAgent, listSeoAgentHealth, listSeoRuns, runSeoAgent, listSeoFindings,
listSeoTasks, approveSeoTask, rejectSeoTask, getDailySeoReport, getWeeklySeoReport,
getSeoOverview`. Every method has a same-shape mock fallback so the dashboard never
breaks offline ("mock now, API next, same DTO"). Dashboard → FastAPI only (never Supabase).

## Wiring status (Phase 1)
- **Live now:** Agent Fleet → `/api/seo/agent-health` (all 16 agents).
- **Adapter-ready (still mock arrays):** Overview, GSC, Indexing, Content Pipeline,
  Hyperlocal, Technical, Competitors, AI Search, Reports, Approvals, Agent Health.
  Swapping each to `seoAgentApi` is mechanical — DTOs already match the row shapes.

## Filters
Every SEO row carries `market/country/city/service` + a date; site-wide rows use
`scope="global"`. Non-geo-filterable cards use the existing `SnapshotBadge`.
