"""Tests for the SEO agent foundation (catalog, runner, approvals, reports, API).

Verifies the acceptance criteria: every agent is visible, every run creates
dashboard-visible findings/recommendations, approval-required work becomes tasks,
approve/reject only change status (no live action), and reports roll up runs.
"""
import pytest
from fastapi.testclient import TestClient

from main import app
from seo_agents import approvals, catalog, reports, runner, store
from seo_agents.schemas import APPROVAL_TASK_TYPES


@pytest.fixture(autouse=True)
def _fresh_store():
    store.reset()
    store.ensure_seeded()
    yield
    store.reset()


# --- catalog ---------------------------------------------------------------
def test_sixteen_agents_all_have_dashboard_and_actions():
    agents = catalog.list_agents()
    assert len(agents) == 16
    assert [a.id for a in agents] == [f"SEO-{i:02d}" for i in range(1, 17)]
    for a in agents:
        assert a.dashboard_sections, f"{a.id} has no dashboard mapping"
        assert "agent-health" in a.dashboard_sections
        # global forbidden actions are always present (no autonomous publish/etc.)
        assert "auto_publish_content" in a.forbidden_actions


def test_every_agent_seeded_a_run_and_findings():
    runs = store.runs()
    assert len(runs) == 16
    run_agents = {r.agent_id for r in runs}
    for a in catalog.list_agents():
        assert a.id in run_agents
    # runs collectively produced findings + recommendations + tasks
    assert len(store.findings()) > 0
    assert len(store.recommendations()) > 0
    assert len(store.tasks()) > 0


def test_findings_carry_filter_fields():
    for f in store.findings():
        # geo rows carry a market; global rows are tagged scope=global
        assert f.market is not None or f.scope == "global"
        assert f.created_at is not None
        assert f.dashboard_section


# --- approval safety -------------------------------------------------------
def test_approval_tasks_use_allowed_types_and_start_pending():
    for t in store.tasks():
        assert t.task_type in APPROVAL_TASK_TYPES
        assert t.approval_status == "pending"


def test_approve_only_changes_status_not_action():
    task = store.tasks()[0]
    updated = approvals.approve(task.task_id, operator="tester")
    assert updated.approval_status == "approved"
    assert updated.assigned_to == "tester"
    # linked recommendation mirrors the decision
    rec = next((r for r in store.recommendations()
                if r.run_id == task.run_id and r.title == task.title), None)
    if rec:
        assert rec.approval_status == "approved"


def test_reject_task():
    task = store.tasks()[-1]
    updated = approvals.reject(task.task_id)
    assert updated.approval_status == "rejected"


def test_reporting_agent_creates_no_approval_tasks():
    seo16 = [t for t in store.tasks() if t.agent_id == "SEO-16"]
    assert seo16 == []


# --- reports ---------------------------------------------------------------
def test_reports_roll_up_all_runs():
    d = reports.daily()
    w = reports.weekly()
    assert d.report_type == "daily"
    assert w.report_type == "weekly"
    assert len(d.agent_run_summary) == 16
    assert d.next_steps and w.next_steps


# --- on-demand run ---------------------------------------------------------
def test_run_agent_appends_new_run():
    before = len(store.runs())
    run = runner.run_agent("SEO-01")
    assert run.agent_id == "SEO-01"
    assert run.status == "completed"
    assert len(store.runs()) == before + 1


def test_unknown_agent_raises():
    with pytest.raises(KeyError):
        runner.run_agent("SEO-99")


# --- API -------------------------------------------------------------------
def test_api_endpoints_smoke():
    client = TestClient(app)
    assert len(client.get("/api/seo/agents").json()) == 16
    assert client.get("/api/seo/agents/SEO-01").json()["id"] == "SEO-01"
    assert client.get("/api/seo/agents/SEO-XX").status_code == 404
    assert len(client.get("/api/seo/agent-health").json()) == 16
    assert client.get("/api/seo/runs").json()
    assert client.get("/api/seo/findings").json()
    assert client.get("/api/seo/tasks?status=pending").json()
    ov = client.get("/api/seo/overview").json()
    assert ov["total_agents"] == 16 and ov["pending_approvals"] > 0
    assert client.get("/api/seo/reports/daily").json()["report_type"] == "daily"
    assert client.get("/api/seo/reports/weekly").json()["report_type"] == "weekly"


def test_api_run_then_approve_flow():
    client = TestClient(app)
    run = client.post("/api/seo/agents/SEO-08/run").json()
    assert run["agent_id"] == "SEO-08"
    tasks = client.get("/api/seo/tasks?agent_id=SEO-08").json()
    assert tasks
    tid = tasks[0]["task_id"]
    approved = client.post(f"/api/seo/tasks/{tid}/approve", json={"operator": "qa"}).json()
    assert approved["approval_status"] == "approved"
    assert client.post("/api/seo/tasks/NOPE/approve").status_code == 404
