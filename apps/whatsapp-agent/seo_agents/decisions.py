"""Approval decision rules for SEO agent output.

Central mapping of which approval task type each agent raises, plus the helpers
the runner uses to decide priority/severity/due dates. RULE: any recommendation
that would change a page, submit a URL, publish content, or start outreach is
approval_required and becomes an approval task — never autonomous.
"""
from __future__ import annotations

from datetime import datetime, timedelta

# agent_id -> the approval task type it raises when a change is recommended.
AGENT_TASK_TYPE: dict[str, str] = {
    "SEO-01": "content_update",
    "SEO-02": "content_update",
    "SEO-03": "content_update",
    "SEO-04": "indexing_resubmission",
    "SEO-05": "content_update",
    "SEO-06": "blog_draft",
    "SEO-07": "content_update",
    "SEO-08": "internal_link_change",
    "SEO-09": "backlink_outreach",
    "SEO-10": "duplicate_merge",
    "SEO-11": "money_page_optimization",
    "SEO-12": "area_page_update",
    "SEO-13": "content_update",
    "SEO-14": "ai_visibility_update",
    "SEO-15": "content_update",
    # SEO-16 raises no approval tasks (reporting only).
}

_SEVERITY = {"urgent": "High", "high": "High", "medium": "Medium", "low": "Low"}
_DUE_DAYS = {"urgent": 1, "high": 3, "medium": 7, "low": 14}


def severity_for(priority: str) -> str:
    return _SEVERITY.get((priority or "").lower(), "Medium")


def due_date_for(priority: str, now: datetime) -> datetime:
    return now + timedelta(days=_DUE_DAYS.get((priority or "").lower(), 7))


def task_type_for(agent_id: str) -> str | None:
    return AGENT_TASK_TYPE.get(agent_id)
