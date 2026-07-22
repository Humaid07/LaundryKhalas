"""Dashboard-ready DTOs for the SEO agent system.

Every field the dashboard filters/renders on is explicit here. Geo fields
(market/country/city/service) + a date field are always present so the admin
global filters (applyGlobalFilters) work on SEO rows exactly like every other
dashboard section. Site-wide rows set ``scope="global"`` so they survive geo
filters instead of vanishing.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

# Approval task types (RULE: any page/content/link/schema/index/outreach change
# must become one of these — never an autonomous action).
APPROVAL_TASK_TYPES = (
    "content_update",
    "blog_draft",
    "internal_link_change",
    "schema_update",
    "indexing_resubmission",
    "backlink_outreach",
    "duplicate_merge",
    "money_page_optimization",
    "area_page_update",
    "ai_visibility_update",
)

APPROVAL_PENDING = "pending"
APPROVAL_APPROVED = "approved"
APPROVAL_REJECTED = "rejected"
APPROVAL_NOT_REQUIRED = "not_required"


class SEOAgent(BaseModel):
    id: str
    name: str
    category: str
    owner: str
    status: str  # Live | Staged | Scheduled | Paused
    mode: str  # monitor-only | draft-only | approval-required
    description: str
    schedule: str
    required_inputs: list[str]
    allowed_actions: list[str]
    forbidden_actions: list[str]
    human_approval_required: bool
    # Dashboard surfaces this agent writes to (route slugs under /seo-agents,
    # plus "agent-health", "approvals", "reports").
    dashboard_sections: list[str]


class SEOFinding(BaseModel):
    finding_id: str
    run_id: str
    agent_id: str
    finding_type: str
    title: str
    description: str
    page_url: str | None = None
    competitor_url: str | None = None
    market: str | None = None
    country: str | None = None
    city: str | None = None
    service: str | None = None
    priority: str  # urgent | high | medium | low
    severity: str  # High | Medium | Low
    impact_reason: str
    recommended_action: str
    dashboard_section: str
    scope: str = "geo"  # "geo" | "global"
    created_at: datetime


class SEORecommendation(BaseModel):
    recommendation_id: str
    run_id: str
    agent_id: str
    title: str
    recommendation_type: str
    page_url: str | None = None
    market: str | None = None
    city: str | None = None
    service: str | None = None
    suggested_change: str
    expected_impact: str
    approval_required: bool
    approval_status: str = APPROVAL_PENDING
    assigned_to: str | None = None
    dashboard_section: str
    created_at: datetime


class SEOApprovalTask(BaseModel):
    task_id: str
    agent_id: str
    run_id: str
    task_type: str
    title: str
    description: str
    page_url: str | None = None
    market: str | None = None
    country: str | None = None
    city: str | None = None
    service: str | None = None
    priority: str
    approval_status: str = APPROVAL_PENDING
    suggested_action: str
    assigned_to: str | None = None
    created_at: datetime
    due_date: datetime | None = None


class DashboardChangeLog(BaseModel):
    change_id: str
    agent_id: str
    run_id: str
    dashboard_section: str
    change_type: str
    before_summary: str
    after_summary: str
    priority: str
    user_visible_message: str
    created_at: datetime


class SEOAgentRun(BaseModel):
    run_id: str
    agent_id: str
    agent_name: str
    status: str  # queued | running | completed | failed
    started_at: datetime
    completed_at: datetime | None = None
    market: str | None = None
    country: str | None = None
    city: str | None = None
    service: str | None = None
    summary: str
    findings_count: int = 0
    recommendations_count: int = 0
    urgent_count: int = 0
    approval_tasks_created: int = 0
    dashboard_sections_affected: list[str] = []
    next_action: str = ""
    cost_estimate: float = 0.0
    source_type: str = "mock"
    mode: str = "monitor-only"


class SEOReport(BaseModel):
    id: str
    report_type: str  # daily | weekly
    generated_at: datetime
    title: str
    wins: list[str]
    risks: list[str]
    urgent_issues: list[str]
    recommended_actions: list[str]
    agent_run_summary: list[dict]
    next_steps: list[str]


class RunAgentRequest(BaseModel):
    market: str | None = None
    country: str | None = None
    city: str | None = None
    service: str | None = None


class ApprovalActionRequest(BaseModel):
    operator: str | None = None
    note: str | None = None
