"""Daily & weekly SEO report generation (SEO-16 output).

Rolls every agent run's findings/recommendations/tasks into a report that always
answers: what changed, why it matters, what to do next — urgent first.
"""
from __future__ import annotations

from datetime import datetime, timezone

from seo_agents import store
from seo_agents.schemas import SEOReport


def _urgent_first(findings):
    order = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
    return sorted(findings, key=lambda f: order.get(f.priority, 4))


def _run_summary() -> list[dict]:
    return [
        {
            "agent_id": r.agent_id,
            "agent_name": r.agent_name,
            "summary": r.summary,
            "findings": r.findings_count,
            "recommendations": r.recommendations_count,
            "approval_tasks": r.approval_tasks_created,
            "urgent": r.urgent_count,
            "sections": r.dashboard_sections_affected,
        }
        for r in store.runs()
    ]


def _build(report_type: str, now: datetime) -> SEOReport:
    findings = store.findings()
    tasks = store.tasks()
    high = [f for f in _urgent_first(findings) if f.priority in ("urgent", "high")]

    wins = [
        f"{f.title}" for f in findings
        if f.finding_type in ("page_gaining", "content_opportunity", "gcc_expansion")
    ][:6]
    risks = [f"{f.title} — {f.impact_reason}" for f in high if f.finding_type in
             ("page_losing", "content_decay", "index_crawled_not_indexed", "index_excluded",
              "duplicate_content", "ai_visibility_gap")][:6]
    urgent_issues = [f"{f.title}" for f in findings if f.priority == "urgent"][:6] or \
        [f"{f.title}" for f in high][:4]
    recommended = [f"Approve/act: {t.title} ({t.priority})" for t in tasks
                   if t.approval_status == "pending"][:8]
    next_steps = [
        "Clear the SEO approval queue (highest priority first)",
        "Resubmit not-indexed pages once approved (no live submit in this phase)",
        "Refresh decaying / losing money pages",
        "Draft approved content opportunities",
    ]

    label = "Daily SEO brief" if report_type == "daily" else "Weekly SEO summary"
    return SEOReport(
        id=f"seo-report-{report_type}",
        report_type=report_type,
        generated_at=now,
        title=f"{label} — {now.date().isoformat()}",
        wins=wins,
        risks=risks,
        urgent_issues=urgent_issues,
        recommended_actions=recommended,
        agent_run_summary=_run_summary(),
        next_steps=next_steps,
    )


def daily(now: datetime | None = None) -> SEOReport:
    return _build("daily", now or datetime.now(timezone.utc))


def weekly(now: datetime | None = None) -> SEOReport:
    return _build("weekly", now or datetime.now(timezone.utc))
