"""SEO Agents API — the ONLY surface the dashboard reads from.

Everything is served from the in-memory SEO store (deterministic mock, seeded on
first access). No live web/Google/GSC/LinkedIn calls. Approve/reject only change
task status — they never perform the underlying publish/edit/submit/outreach.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from seo_agents import approvals, dashboard_data, reports, runner, store
from seo_agents.catalog import get_agent, list_agents
from seo_agents.schemas import (
    ApprovalActionRequest,
    RunAgentRequest,
    SEOAgent,
    SEOAgentRun,
    SEOApprovalTask,
    SEOFinding,
    SEORecommendation,
    SEOReport,
)

router = APIRouter(prefix="/api/seo", tags=["seo-agents"])


# --- catalog ---------------------------------------------------------------
@router.get("/agents", response_model=list[SEOAgent])
async def list_seo_agents():
    return list_agents()


@router.get("/agents/{agent_id}", response_model=SEOAgent)
async def get_seo_agent(agent_id: str):
    agent = get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="SEO agent not found.")
    return agent


# --- Dev & Automation / Agent Health --------------------------------------
@router.get("/agent-health")
async def agent_health():
    """One row per agent for the Dev & Automation → Agent Health table."""
    rows = []
    for a in list_agents():
        last = store.latest_run_for(a.id)
        rows.append({
            "agent_id": a.id,
            "name": a.name,
            "category": a.category,
            "status": a.status,
            "mode": a.mode,
            "owner": a.owner,
            "schedule": a.schedule,
            "last_run": last.completed_at if last else None,
            "next_run": a.schedule,
            "success_rate": 100.0 if last and last.status == "completed" else 0.0,
            "avg_latency": "0.4s",
            "cost_today": round(a.__hash__() % 3 * 0.1, 2) if False else 0.0,
            "issues": last.urgent_count if last else 0,
            "findings": last.findings_count if last else 0,
            "approval_tasks": last.approval_tasks_created if last else 0,
            "dashboard_sections": a.dashboard_sections,
            "human_approval_required": a.human_approval_required,
        })
    return rows


# --- runs ------------------------------------------------------------------
@router.get("/runs", response_model=list[SEOAgentRun])
async def list_runs(agent_id: str | None = None):
    rows = store.runs()
    if agent_id:
        rows = [r for r in rows if r.agent_id == agent_id]
    return list(reversed(rows))  # newest first


@router.get("/runs/{run_id}", response_model=SEOAgentRun)
async def get_run(run_id: str):
    run = store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    return run


@router.post("/agents/{agent_id}/run", response_model=SEOAgentRun)
async def run_seo_agent(agent_id: str, payload: RunAgentRequest | None = None):
    if get_agent(agent_id) is None:
        raise HTTPException(status_code=404, detail="SEO agent not found.")
    ctx = (payload.model_dump(exclude_none=True) if payload else {})
    return runner.run_agent(agent_id, ctx)


# --- findings / recommendations / change log ------------------------------
@router.get("/findings", response_model=list[SEOFinding])
async def list_findings(agent_id: str | None = None, section: str | None = None):
    rows = store.findings()
    if agent_id:
        rows = [f for f in rows if f.agent_id == agent_id]
    if section:
        rows = [f for f in rows if f.dashboard_section == section]
    return rows


@router.get("/recommendations", response_model=list[SEORecommendation])
async def list_recommendations(agent_id: str | None = None):
    rows = store.recommendations()
    if agent_id:
        rows = [r for r in rows if r.agent_id == agent_id]
    return rows


@router.get("/changes")
async def list_changes():
    return list(reversed(store.changes()))


# --- approval queue --------------------------------------------------------
@router.get("/tasks", response_model=list[SEOApprovalTask])
async def list_tasks(status: str | None = None, agent_id: str | None = None):
    rows = store.tasks()
    if status:
        rows = [t for t in rows if t.approval_status == status]
    if agent_id:
        rows = [t for t in rows if t.agent_id == agent_id]
    return rows


@router.post("/tasks/{task_id}/approve", response_model=SEOApprovalTask)
async def approve_task(task_id: str, payload: ApprovalActionRequest | None = None):
    operator = payload.operator if payload else None
    task = approvals.approve(task_id, operator)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")
    return task


@router.post("/tasks/{task_id}/reject", response_model=SEOApprovalTask)
async def reject_task(task_id: str, payload: ApprovalActionRequest | None = None):
    operator = payload.operator if payload else None
    task = approvals.reject(task_id, operator)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")
    return task


# --- reports ---------------------------------------------------------------
@router.get("/reports/daily", response_model=SEOReport)
async def daily_report():
    return reports.daily()


@router.get("/reports/weekly", response_model=SEOReport)
async def weekly_report():
    return reports.weekly()


# --- dashboard subsection tables ------------------------------------------
# Served in the exact shapes the admin subsection tables render (see
# seo_agents/dashboard_data.py). Rows carry market/city/service (+ scope=global
# for site-wide rows) so the dashboard global filters slice them.
@router.get("/dashboard/gsc-pages")
async def dashboard_gsc_pages():
    return dashboard_data.GSC_PAGES


@router.get("/dashboard/indexing")
async def dashboard_indexing():
    return dashboard_data.INDEXING_QUEUE


@router.get("/dashboard/hyperlocal")
async def dashboard_hyperlocal():
    return dashboard_data.HYPERLOCAL_PAGES


@router.get("/dashboard/technical-issues")
async def dashboard_technical_issues():
    return dashboard_data.TECH_SEO_ISSUES


@router.get("/dashboard/competitors")
async def dashboard_competitors():
    return dashboard_data.COMPETITORS


@router.get("/dashboard/ai-search")
async def dashboard_ai_search():
    return dashboard_data.AI_SEARCH


# --- overview KPIs ---------------------------------------------------------
@router.get("/overview")
async def overview():
    agents = list_agents()
    runs = store.runs()
    findings = store.findings()
    tasks = store.tasks()
    gaining = [f for f in findings if f.finding_type == "page_gaining"]
    losing = [f for f in findings if f.finding_type == "page_losing"]
    indexing_issues = [f for f in findings if f.finding_type.startswith("index_")]
    content_opps = [f for f in findings if f.finding_type == "content_opportunity"]
    return {
        "active_agents": sum(1 for a in agents if a.status in ("Live", "Scheduled", "Staged")),
        "total_agents": len(agents),
        "runs_today": len(runs),
        "urgent_issues": sum(1 for f in findings if f.priority == "urgent"),
        "high_issues": sum(1 for f in findings if f.priority == "high"),
        "pages_gaining": len(gaining),
        "pages_losing": len(losing),
        "indexing_issues": len(indexing_issues),
        "pending_approvals": sum(1 for t in tasks if t.approval_status == "pending"),
        "content_opportunities": len(content_opps),
        "total_findings": len(findings),
    }
