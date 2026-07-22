"""In-memory store for SEO agent state (Phase 1).

Deliberately NOT backed by Supabase — this keeps the SEO build fully isolated
from the live WhatsApp/Evolution schema and needs no migration. State is seeded
deterministically at first use (from mock sources) so the dashboard always has
data, and resets on process restart (documented limitation for Phase 1).
"""
from __future__ import annotations

from itertools import count

from seo_agents.schemas import (
    DashboardChangeLog,
    SEOAgentRun,
    SEOApprovalTask,
    SEOFinding,
    SEORecommendation,
)

_runs: list[SEOAgentRun] = []
_findings: list[SEOFinding] = []
_recs: list[SEORecommendation] = []
_tasks: list[SEOApprovalTask] = []
_changes: list[DashboardChangeLog] = []

_counters: dict[str, count] = {}
_ID_PREFIX = {"run": "RUN", "finding": "FND", "rec": "REC", "task": "TSK", "change": "CHG"}
_seeded = False


def next_id(kind: str) -> str:
    c = _counters.setdefault(kind, count(1))
    return f"{_ID_PREFIX[kind]}-{next(c):04d}"


def record_run(
    run: SEOAgentRun,
    findings: list[SEOFinding],
    recs: list[SEORecommendation],
    tasks: list[SEOApprovalTask],
    change: DashboardChangeLog,
) -> None:
    _runs.append(run)
    _findings.extend(findings)
    _recs.extend(recs)
    _tasks.extend(tasks)
    _changes.append(change)


def ensure_seeded() -> None:
    """Seed the store by running every agent once against the fixed mock clock.
    Idempotent — safe to call from API handlers/tests."""
    global _seeded
    if _seeded:
        return
    _seeded = True  # set first so a re-entrant import can't double-seed
    from seo_agents import mock_sources as ms
    from seo_agents import runner

    runner.run_all(now=ms.MOCK_NOW)


def reset() -> None:
    """Clear all state (tests only)."""
    global _seeded
    _runs.clear()
    _findings.clear()
    _recs.clear()
    _tasks.clear()
    _changes.clear()
    _counters.clear()
    _seeded = False


# --- read accessors (API/reports filter on top of these) -------------------
def runs() -> list[SEOAgentRun]:
    ensure_seeded()
    return list(_runs)


def findings() -> list[SEOFinding]:
    ensure_seeded()
    return list(_findings)


def recommendations() -> list[SEORecommendation]:
    ensure_seeded()
    return list(_recs)


def tasks() -> list[SEOApprovalTask]:
    ensure_seeded()
    return list(_tasks)


def changes() -> list[DashboardChangeLog]:
    ensure_seeded()
    return list(_changes)


def get_run(run_id: str) -> SEOAgentRun | None:
    return next((r for r in runs() if r.run_id == run_id), None)


def get_task(task_id: str) -> SEOApprovalTask | None:
    ensure_seeded()
    return next((t for t in _tasks if t.task_id == task_id), None)


def latest_run_for(agent_id: str) -> SEOAgentRun | None:
    matches = [r for r in runs() if r.agent_id == agent_id]
    return matches[-1] if matches else None
