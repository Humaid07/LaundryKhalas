"""Approval queue actions for SEO tasks.

Approving/rejecting a task here ONLY updates the task's status and the linked
recommendation — it NEVER performs the underlying action (no publish, no page
edit, no Search Console submit, no outreach). Those remain manual/out of scope
for Phase 1.
"""
from __future__ import annotations

from seo_agents import store
from seo_agents.schemas import APPROVAL_APPROVED, APPROVAL_REJECTED, SEOApprovalTask


def _set_status(task_id: str, status: str, operator: str | None) -> SEOApprovalTask | None:
    task = store.get_task(task_id)
    if task is None:
        return None
    task.approval_status = status
    if operator:
        task.assigned_to = operator
    # Mirror onto the linked recommendation(s) of the same run/agent so the
    # dashboard recommendation view reflects the decision.
    for rec in store.recommendations():
        if rec.run_id == task.run_id and rec.agent_id == task.agent_id and rec.approval_required:
            if rec.title == task.title:
                rec.approval_status = status
                if operator:
                    rec.assigned_to = operator
    return task


def approve(task_id: str, operator: str | None = None) -> SEOApprovalTask | None:
    """Mark a task approved. Does NOT execute the action — it stays a manual,
    human-performed step outside this system in Phase 1."""
    return _set_status(task_id, APPROVAL_APPROVED, operator)


def reject(task_id: str, operator: str | None = None) -> SEOApprovalTask | None:
    return _set_status(task_id, APPROVAL_REJECTED, operator)
