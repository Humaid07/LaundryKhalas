"""Mock SEO agent runners.

Each agent turns its deterministic mock source into dashboard-ready findings +
recommendations. The generic ``run_agent`` wraps a producer: it stamps ids/times,
creates an approval task for every approval-required recommendation (so nothing
is autonomous), writes a DashboardChangeLog, records an SEOAgentRun, and appends
it all to the in-memory store.

Producers are intentionally simple/deterministic — no LLM, no web calls.
"""
from __future__ import annotations

from datetime import datetime, timezone

from seo_agents import mock_sources as ms
from seo_agents import store as _store
from seo_agents.catalog import get_agent
from seo_agents.decisions import due_date_for, severity_for, task_type_for
from seo_agents.schemas import (
    APPROVAL_PENDING,
    DashboardChangeLog,
    SEOAgent,
    SEOAgentRun,
    SEOApprovalTask,
    SEOFinding,
    SEORecommendation,
)

# --- per-agent producers: (agent, ctx) -> (summary, findings[], recs[]) -----
# findings/recs are plain dicts with the fields the DTOs need; the primary
# dashboard_section defaults to agent.dashboard_sections[0] when omitted.


def _sec(agent: SEOAgent) -> str:
    return agent.dashboard_sections[0]


def _seo01(agent, ctx):
    findings = [
        {"finding_type": c["change_type"], "title": f"Competitor change: {c['change_type'].replace('_',' ')}",
         "description": c["detail"], "competitor_url": c["competitor_url"], "market": c["market"],
         "city": c["city"], "service": c["service"], "priority": c["priority"],
         "impact_reason": "Competitor is strengthening a page we compete on",
         "recommended_action": "Review and consider matching on our page"}
        for c in ms.COMPETITOR_PAGES[:4]
    ]
    recs = [
        {"title": f"Match competitor FAQ/content on {c['service']} {c['city']}",
         "page_url": f"/{c['service'].lower().replace(' ','-')}-{c['city'].lower().replace(' ','-')}",
         "market": c["market"], "city": c["city"], "service": c["service"],
         "suggested_change": c["detail"], "expected_impact": "Defend ranking / close content gap"}
        for c in ms.COMPETITOR_PAGES[:2]
    ]
    return "Checked 5 competitor pages; detected FAQ, new-page and content changes.", findings, recs


def _seo02(agent, ctx):
    findings = [
        {"finding_type": "trend_alert", "title": t["title"], "description": "Rising industry/news trend",
         "market": t["market"], "city": t["city"], "service": t["service"], "priority": t["urgency"],
         "impact_reason": "Timely topic with rising demand", "recommended_action": "Draft aligned content"}
        for t in ms.TREND_ALERTS
    ]
    recs = [
        {"title": f"Content opportunity: {t['title']}", "market": t["market"], "city": t["city"],
         "service": t["service"], "suggested_change": "Draft an article aligned to this trend",
         "expected_impact": "Capture rising search demand"}
        for t in ms.TREND_ALERTS[:2]
    ]
    return "Scanned industry/news trends; found 3 content opportunities.", findings, recs


def _seo03(agent, ctx):
    findings = []
    for p in ms.GSC_PAGES[:6]:
        gaining = p["delta"] >= 0
        findings.append({
            "finding_type": "page_gaining" if gaining else "page_losing",
            "title": f"{p['page_url']} {'gaining' if gaining else 'losing'} ({p['delta']:+d} clicks)",
            "description": f"clicks {p['clicks']}, impressions {p['impressions']}, pos {p['position']}",
            "page_url": p["page_url"], "market": p["market"], "city": p["city"], "service": p["service"],
            "priority": "high" if (not gaining and p["delta"] < -20) else "medium" if not gaining else "low",
            "impact_reason": "Visibility change vs prior day",
            "recommended_action": "Refresh losing pages; reinforce gaining ones"})
    recs = [
        {"title": f"Refresh losing page {p['page_url']}", "page_url": p["page_url"], "market": p["market"],
         "city": p["city"], "service": p["service"], "suggested_change": "Refresh content + internal links",
         "expected_impact": "Recover lost clicks/position"}
        for p in ms.GSC_PAGES if p["delta"] < -20
    ][:3]
    return "Reviewed last-24h GSC (mock): flagged gaining/losing pages.", findings, recs


def _seo04(agent, ctx):
    bad = [r for r in ms.INDEXING_ROWS if r["state"] in ("crawled_not_indexed", "pending", "excluded")]
    findings = [
        {"finding_type": f"index_{r['state']}", "title": f"{r['page_url']} — {r['state'].replace('_',' ')}",
         "description": "URL not fully indexed", "page_url": r["page_url"], "market": r["market"],
         "city": r["city"], "service": r["service"], "priority": "high" if r["state"] != "pending" else "medium",
         "impact_reason": "Page cannot rank while not indexed",
         "recommended_action": "Prepare resubmission (approval required)"}
        for r in bad
    ]
    recs = [
        {"title": f"Resubmit {r['page_url']} to Search Console", "page_url": r["page_url"], "market": r["market"],
         "city": r["city"], "service": r["service"], "suggested_change": "Queue URL for resubmission",
         "expected_impact": "Get page indexed and eligible to rank"}
        for r in bad[:3]
    ]
    return "Tracked index status; prepared resubmission tasks (no live submit).", findings, recs


def _opps_producer(items, section_note):
    def producer(agent, ctx):
        findings = [
            {"finding_type": "content_opportunity", "title": o["title"], "description": section_note,
             "market": o.get("market"), "city": o.get("city"), "service": o.get("service"),
             "priority": o.get("priority", "medium"), "impact_reason": "Gap / unmet intent",
             "recommended_action": "Draft content (approval required)"}
            for o in items[:4]
        ]
        recs = [
            {"title": f"Draft: {o['title']}", "market": o.get("market"), "city": o.get("city"),
             "service": o.get("service"), "suggested_change": "Create outline + FAQ, recommend schema",
             "expected_impact": "New/updated ranking content"}
            for o in items[:2]
        ]
        return f"Produced {len(findings)} opportunities.", findings, recs
    return producer


def _seo06(agent, ctx):
    o = ms.CONTENT_OPPORTUNITIES[0]
    findings = [{"finding_type": "blog_brief", "title": f"Blog brief: {o['title']}",
                 "description": "Outline + FAQ + schema recommendation prepared",
                 "market": o["market"], "city": o["city"], "service": o["service"], "priority": "high",
                 "impact_reason": "High-intent topic ready to draft",
                 "recommended_action": "Approve draft before publishing"}]
    recs = [{"title": f"Approve blog draft: {o['title']}", "market": o["market"], "city": o["city"],
             "service": o["service"], "suggested_change": "Publish outline as Article + FAQ schema",
             "expected_impact": "New ranking article with FAQ eligibility"}]
    return "Drafted 1 blog outline with FAQ + schema recommendations (not published).", findings, recs


def _seo08(agent, ctx):
    findings = [
        {"finding_type": "orphan_page" if o["orphan"] else "internal_link_gap",
         "title": f"{'Orphan' if o['orphan'] else 'Weak link'}: {o['page_url']} → {o['target_money_page']}",
         "description": o["reason"], "page_url": o["page_url"], "market": o["market"], "city": o["city"],
         "service": o["service"], "priority": o["priority"], "impact_reason": "Money page under-supported",
         "recommended_action": "Add internal link (approval required)"}
        for o in ms.INTERNAL_LINK_OPPS[:4]
    ]
    recs = [
        {"title": f"Link {o['page_url']} → {o['target_money_page']}", "page_url": o["page_url"],
         "market": o["market"], "city": o["city"], "service": o["service"],
         "suggested_change": f"Add contextual internal link to {o['target_money_page']}",
         "expected_impact": "Stronger money-page support"}
        for o in ms.INTERNAL_LINK_OPPS[:3]
    ]
    return "Found orphan pages + internal-link opportunities.", findings, recs


def _seo09(agent, ctx):
    findings = [
        {"finding_type": f"backlink_{b['type']}", "title": f"{b['type'].replace('_',' ').title()}: {b['source']}",
         "description": f"authority {b['authority']} · {b['cost']}", "market": b["market"], "city": b["city"],
         "service": b["service"], "priority": b["priority"], "impact_reason": "Relevant linking opportunity",
         "recommended_action": "Approve outreach/placement"}
        for b in ms.BACKLINK_OPPORTUNITIES[:4]
    ]
    recs = [
        {"title": f"Outreach: {b['source']}", "market": b["market"], "city": b["city"], "service": b["service"],
         "suggested_change": f"{b['cost']} {b['type']} link", "expected_impact": "Referring domain + authority"}
        for b in ms.BACKLINK_OPPORTUNITIES[:2]
    ]
    return "Scored backlink opportunities (no outreach sent).", findings, recs


def _seo10(agent, ctx):
    findings = [
        {"finding_type": "duplicate_content", "title": f"{d['page_url']} ~ {d['other_url']}",
         "description": f"{d['overlap']} → recommend {d['recommendation']}", "page_url": d["page_url"],
         "market": d["market"], "city": d["city"], "service": d["service"], "priority": d["priority"],
         "impact_reason": "Intent overlap dilutes both pages",
         "recommended_action": f"{d['recommendation']} (approval required)"}
        for d in ms.DUPLICATE_FINDINGS[:4]
    ]
    recs = [
        {"title": f"{d['recommendation'].title()} {d['page_url']} & {d['other_url']}", "page_url": d["page_url"],
         "market": d["market"], "city": d["city"], "service": d["service"],
         "suggested_change": f"{d['recommendation']} the two pages", "expected_impact": "Consolidated ranking signal"}
        for d in ms.DUPLICATE_FINDINGS[:2]
    ]
    return "Detected duplicates by intent overlap + usefulness.", findings, recs


def _recs_producer(items, finding_type):
    def producer(agent, ctx):
        findings = [
            {"finding_type": finding_type, "title": f"{r['page_url']}: {r['gap']}", "description": r["suggestion"],
             "page_url": r["page_url"], "market": r["market"], "city": r["city"], "service": r["service"],
             "priority": r["priority"], "impact_reason": r["gap"], "recommended_action": r["suggestion"]}
            for r in items[:4]
        ]
        recs = [
            {"title": f"Optimize {r['page_url']}", "page_url": r["page_url"], "market": r["market"],
             "city": r["city"], "service": r["service"], "suggested_change": r["suggestion"],
             "expected_impact": "Improved relevance / coverage"}
            for r in items[:3]
        ]
        return f"Produced {len(findings)} page recommendations.", findings, recs
    return producer


def _seo13(agent, ctx):
    findings = [
        {"finding_type": "content_decay", "title": f"Decay: {p['page_url']} ({p['delta']:+d})",
         "description": "Losing impressions/clicks vs trend", "page_url": p["page_url"], "market": p["market"],
         "city": p["city"], "service": p["service"], "priority": "high",
         "impact_reason": "Declining visibility", "recommended_action": "Refresh/expand or merge"}
        for p in ms.DECAY_PAGES
    ]
    recs = [
        {"title": f"Refresh decaying page {p['page_url']}", "page_url": p["page_url"], "market": p["market"],
         "city": p["city"], "service": p["service"], "suggested_change": "Refresh + de-cannibalize",
         "expected_impact": "Recover visibility"}
        for p in ms.DECAY_PAGES[:2]
    ]
    return "Found decaying pages + cannibalization risks.", findings, recs


def _seo14(agent, ctx):
    findings = [
        {"finding_type": "ai_visibility_gap", "title": f"{r['page_url']}: {r['gap']}", "description": r["suggestion"],
         "page_url": r["page_url"], "market": r["market"], "city": r["city"], "service": r["service"],
         "priority": r["priority"], "impact_reason": "Not extractable for AI answers",
         "recommended_action": r["suggestion"]}
        for r in ms.AI_VISIBILITY_RECS[:4]
    ]
    recs = [
        {"title": f"Add extractable structure: {r['page_url']}", "page_url": r["page_url"], "market": r["market"],
         "city": r["city"], "service": r["service"], "suggested_change": r["suggestion"],
         "expected_impact": "Eligibility in AI overviews"}
        for r in ms.AI_VISIBILITY_RECS[:2]
    ]
    return "Assessed AI extractability; suggested direct-answer/FAQ blocks.", findings, recs


def _seo15(agent, ctx):
    findings = [
        {"finding_type": "gcc_expansion", "title": o["title"], "description": "New GCC market opportunity",
         "market": o["market"], "city": o["city"], "service": o["service"], "priority": o["priority"],
         "impact_reason": "Untapped GCC market", "recommended_action": "Draft localized page (approval required)"}
        for o in ms.GCC_EXPANSION_OPPS
    ]
    recs = [
        {"title": f"Create localized page: {o['title']}", "market": o["market"], "city": o["city"],
         "service": o["service"], "suggested_change": "Draft country-subfolder localized page",
         "expected_impact": "Enter new GCC market"}
        for o in ms.GCC_EXPANSION_OPPS[:2]
    ]
    return "Suggested GCC country-subfolder pages from market config.", findings, recs


def _seo16(agent, ctx):
    # Reporting agent produces no findings/recs — it rolls up others into reports.
    return "Compiled daily + weekly SEO reports from all agent runs.", [], []


PRODUCERS = {
    "SEO-01": _seo01, "SEO-02": _seo02, "SEO-03": _seo03, "SEO-04": _seo04,
    "SEO-05": _opps_producer(ms.CONTENT_OPPORTUNITIES, "Content research opportunity"),
    "SEO-06": _seo06,
    "SEO-07": _opps_producer(ms.TOPICAL_GAPS_AS_OPPS if hasattr(ms, "TOPICAL_GAPS_AS_OPPS") else
                             [{"title": f"Add subtopic: {g['missing_subtopic']} ({g['cluster']})", **g}
                              for g in ms.TOPICAL_GAPS], "Topical authority gap"),
    "SEO-08": _seo08, "SEO-09": _seo09, "SEO-10": _seo10,
    "SEO-11": _recs_producer(ms.MONEY_PAGE_RECS, "money_page_gap"),
    "SEO-12": _recs_producer(ms.AREA_PAGE_RECS, "area_page_gap"),
    "SEO-13": _seo13, "SEO-14": _seo14, "SEO-15": _seo15, "SEO-16": _seo16,
}


def run_agent(agent_id: str, ctx: dict | None = None, *, now: datetime | None = None) -> SEOAgentRun:
    """Run one agent against mock sources; append run + findings + recs + tasks +
    change log to the store. Returns the SEOAgentRun."""
    agent = get_agent(agent_id)
    if agent is None:
        raise KeyError(f"Unknown SEO agent: {agent_id}")
    ctx = ctx or {}
    now = now or datetime.now(timezone.utc)
    producer = PRODUCERS[agent_id]
    summary, findings_data, recs_data = producer(agent, ctx)

    run_id = _store.next_id("run")
    primary = _sec(agent)
    findings: list[SEOFinding] = []
    recs: list[SEORecommendation] = []
    tasks: list[SEOApprovalTask] = []
    urgent = 0

    for fd in findings_data:
        pr = fd.get("priority", "medium")
        if pr == "urgent":
            urgent += 1
        findings.append(SEOFinding(
            finding_id=_store.next_id("finding"), run_id=run_id, agent_id=agent_id,
            finding_type=fd["finding_type"], title=fd["title"], description=fd["description"],
            page_url=fd.get("page_url"), competitor_url=fd.get("competitor_url"),
            market=fd.get("market"), country=fd.get("market"), city=fd.get("city"),
            service=fd.get("service"), priority=pr, severity=severity_for(pr),
            impact_reason=fd["impact_reason"], recommended_action=fd["recommended_action"],
            dashboard_section=fd.get("dashboard_section", primary),
            scope="global" if fd.get("market") is None else "geo", created_at=now))

    task_type = task_type_for(agent_id)
    for rd in recs_data:
        approval_required = agent.human_approval_required and task_type is not None
        rec = SEORecommendation(
            recommendation_id=_store.next_id("rec"), run_id=run_id, agent_id=agent_id,
            title=rd["title"], recommendation_type=task_type or "report",
            page_url=rd.get("page_url"), market=rd.get("market"), city=rd.get("city"),
            service=rd.get("service"), suggested_change=rd["suggested_change"],
            expected_impact=rd["expected_impact"], approval_required=approval_required,
            approval_status=APPROVAL_PENDING if approval_required else "not_required",
            dashboard_section=rd.get("dashboard_section", primary), created_at=now)
        recs.append(rec)
        if approval_required:
            pr = rd.get("priority", "high")
            tasks.append(SEOApprovalTask(
                task_id=_store.next_id("task"), agent_id=agent_id, run_id=run_id, task_type=task_type,
                title=rd["title"], description=rec.suggested_change, page_url=rec.page_url,
                market=rec.market, country=rec.market, city=rec.city, service=rec.service,
                priority=pr, approval_status=APPROVAL_PENDING, suggested_action=rec.suggested_change,
                created_at=now, due_date=due_date_for(pr, now)))

    sections_affected = sorted({f.dashboard_section for f in findings} | {r.dashboard_section for r in recs}
                               | set(agent.dashboard_sections))
    run = SEOAgentRun(
        run_id=run_id, agent_id=agent_id, agent_name=agent.name, status="completed",
        started_at=now, completed_at=now, market=ctx.get("market"), country=ctx.get("country"),
        city=ctx.get("city"), service=ctx.get("service"), summary=summary,
        findings_count=len(findings), recommendations_count=len(recs), urgent_count=urgent,
        approval_tasks_created=len(tasks), dashboard_sections_affected=sections_affected,
        next_action="Review findings and approve/reject tasks" if tasks else "Review findings",
        cost_estimate=0.0, source_type="mock", mode=agent.mode)

    change = DashboardChangeLog(
        change_id=_store.next_id("change"), agent_id=agent_id, run_id=run_id,
        dashboard_section=primary, change_type="run_completed",
        before_summary="Previous state", after_summary=summary, priority="high" if urgent else "medium",
        user_visible_message=f"{agent.name}: {summary} ({len(findings)} findings, {len(tasks)} approvals)",
        created_at=now)

    _store.record_run(run, findings, recs, tasks, change)
    return run


def run_all(*, now: datetime | None = None) -> list[SEOAgentRun]:
    """Run every agent once (used to seed the store)."""
    from seo_agents.catalog import list_agents
    return [run_agent(a.id, now=now) for a in list_agents()]
