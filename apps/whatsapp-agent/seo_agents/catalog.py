"""The SEO agent catalog — the single source of truth for the 16 agents.

Each agent declares its dashboard surfaces (so there are no invisible
backend-only agents), its required inputs, and its allowed/forbidden actions.
Every agent that can change a page / submit a URL / publish / do outreach has
``human_approval_required=True`` and lists those as FORBIDDEN autonomous
actions — the runner turns them into approval tasks instead.
"""
from __future__ import annotations

from seo_agents.schemas import SEOAgent

# Actions no SEO agent may ever do autonomously in any phase.
_GLOBAL_FORBIDDEN = [
    "auto_publish_content",
    "auto_update_website_page",
    "auto_submit_search_console_url",
    "auto_send_outreach",
    "auto_buy_backlinks",
    "invent_reviews_stats_rankings_prices_claims",
]

_MONITOR = "monitor-only"
_DRAFT = "draft-only"
_APPROVAL = "approval-required"


def _agent(
    id: str,
    name: str,
    *,
    mode: str,
    description: str,
    schedule: str,
    required_inputs: list[str],
    allowed_actions: list[str],
    forbidden_actions: list[str],
    human_approval_required: bool,
    dashboard_sections: list[str],
    owner: str = "SEO Team",
    status: str = "Staged",
) -> SEOAgent:
    return SEOAgent(
        id=id,
        name=name,
        category="SEO",
        owner=owner,
        status=status,
        mode=mode,
        description=description,
        schedule=schedule,
        required_inputs=required_inputs,
        allowed_actions=allowed_actions,
        forbidden_actions=forbidden_actions + _GLOBAL_FORBIDDEN,
        human_approval_required=human_approval_required,
        dashboard_sections=dashboard_sections,
    )


# Ordered SEO-01 .. SEO-16.
_CATALOG: list[SEOAgent] = [
    _agent(
        "SEO-01", "Competitor Monitor", mode=_MONITOR,
        description="Checks up to 5 competitor pages daily for new/removed pages, "
        "content, layout, internal-link and FAQ changes; flags ranking movement "
        "and backlink opportunities.",
        schedule="Daily · 06:00",
        required_inputs=["competitor_urls", "target_market", "target_service", "target_keywords"],
        allowed_actions=["monitor_competitors", "draft_priority_recommendations"],
        forbidden_actions=["change_our_pages", "start_outreach"],
        human_approval_required=True,
        dashboard_sections=["competitors", "overview", "reports", "agent-health"],
    ),
    _agent(
        "SEO-02", "News & Industry Trend Monitor", mode=_MONITOR,
        description="Scans Google-News / LinkedIn-style industry content for laundry, "
        "dry cleaning, fabric care, commercial laundry and GCC trends.",
        schedule="Daily · 07:00",
        required_inputs=["target_market", "target_keywords"],
        allowed_actions=["monitor_trends", "draft_content_opportunities"],
        forbidden_actions=["draft_publication", "start_outreach"],
        human_approval_required=True,
        dashboard_sections=["content-pipeline", "reports", "agent-health"],
    ),
    _agent(
        "SEO-03", "Google Search Console Monitor", mode=_MONITOR,
        description="Reviews last-24h clicks, impressions, position and CTR; flags "
        "gaining/losing pages and new indexing issues. Mock GSC data until live "
        "GSC is approved.",
        schedule="Daily · 05:30",
        required_inputs=["gsc_property", "target_market"],
        allowed_actions=["read_gsc_mock", "draft_recommended_actions"],
        forbidden_actions=["change_our_pages"],
        human_approval_required=True,
        dashboard_sections=["gsc-performance", "overview", "reports", "agent-health"],
    ),
    _agent(
        "SEO-04", "Indexing & Sitemap Agent", mode=_APPROVAL,
        description="Tracks URL status (indexed/pending/excluded/crawled-not-indexed) "
        "and PREPARES resubmission actions. Does not submit to Search Console.",
        schedule="Daily · 08:00",
        required_inputs=["sitemap_url", "gsc_property"],
        allowed_actions=["track_index_status", "prepare_resubmission_task"],
        forbidden_actions=["submit_search_console_url"],
        human_approval_required=True,
        dashboard_sections=["indexing", "reports", "approvals", "agent-health"],
    ),
    _agent(
        "SEO-05", "Content Research Agent", mode=_MONITOR,
        description="Researches questions/trends/customer problems (Google/forums/"
        "Quora/Reddit/Trends style, mock sources) grouped by intent; finds gaps and "
        "Emirate-specific blog opportunities.",
        schedule="Daily · 09:00",
        required_inputs=["target_market", "target_service", "seed_topics"],
        allowed_actions=["research_topics", "draft_content_opportunities"],
        forbidden_actions=["publish_content"],
        human_approval_required=True,
        dashboard_sections=["content-pipeline", "hyperlocal-pages", "reports", "agent-health"],
    ),
    _agent(
        "SEO-06", "Blog + Schema Draft Agent", mode=_DRAFT,
        description="Drafts blog outlines/content in simple English with an FAQ "
        "section and recommends Article/FAQ/LocalBusiness/Service/Product/Review "
        "schema. Never publishes automatically.",
        schedule="On demand",
        required_inputs=["blog_brief", "target_keywords", "target_market"],
        allowed_actions=["draft_blog_outline", "recommend_schema", "suggest_internal_links"],
        forbidden_actions=["publish_content", "update_website_page"],
        human_approval_required=True,
        dashboard_sections=["content-pipeline", "reports", "approvals", "agent-health"],
    ),
    _agent(
        "SEO-07", "Topical Authority Agent", mode=_MONITOR,
        description="Builds/maintains topic clusters (laundry, dry cleaning, shoe/"
        "carpet/curtain cleaning, fabric care, commercial laundry); finds missing "
        "subtopics and suggests pillar + supporting pages.",
        schedule="Weekly · Mon",
        required_inputs=["target_service", "existing_pages"],
        allowed_actions=["map_clusters", "suggest_pillar_pages"],
        forbidden_actions=["publish_content"],
        human_approval_required=True,
        dashboard_sections=["content-pipeline", "hyperlocal-pages", "reports", "agent-health"],
    ),
    _agent(
        "SEO-08", "Internal Linking Agent", mode=_APPROVAL,
        description="Finds orphan pages and suggests internal links from blogs/service/"
        "area pages to money pages; scores money-page support.",
        schedule="Weekly · Tue",
        required_inputs=["site_pages", "money_pages"],
        allowed_actions=["find_orphans", "suggest_internal_links"],
        forbidden_actions=["edit_pages"],
        human_approval_required=True,
        dashboard_sections=["technical-seo", "content-pipeline", "reports", "approvals", "agent-health"],
    ),
    _agent(
        "SEO-09", "Backlink Opportunity Agent", mode=_APPROVAL,
        description="Finds free/paid backlink opportunities (directories, resource "
        "pages, guest posts, citations, mentions) and scores by relevance/authority.",
        schedule="Weekly · Wed",
        required_inputs=["target_market", "target_service"],
        allowed_actions=["find_backlink_opportunities", "score_opportunities"],
        forbidden_actions=["send_outreach", "buy_backlinks"],
        human_approval_required=True,
        dashboard_sections=["competitors", "reports", "approvals", "agent-health"],
    ),
    _agent(
        "SEO-10", "Duplicate Content Agent", mode=_MONITOR,
        description="Detects duplicate/near-duplicate/repetitive content judged by "
        "usefulness + intent overlap (not a fixed percentage) and recommends "
        "rephrase/merge/canonical/consolidation.",
        schedule="Weekly · Thu",
        required_inputs=["site_pages"],
        allowed_actions=["detect_duplicates", "recommend_consolidation"],
        forbidden_actions=["merge_pages", "set_canonical"],
        human_approval_required=True,
        dashboard_sections=["technical-seo", "reports", "approvals", "agent-health"],
    ),
    _agent(
        "SEO-11", "Money Page Optimization Agent", mode=_APPROVAL,
        description="Reviews service/landing pages for entity coverage, attributes, "
        "values, LSI + primary keywords in headings and readability. No keyword "
        "stuffing.",
        schedule="Weekly · Fri",
        required_inputs=["money_pages", "target_keywords"],
        allowed_actions=["audit_money_page", "suggest_keywords", "suggest_headings"],
        forbidden_actions=["edit_pages"],
        human_approval_required=True,
        dashboard_sections=["technical-seo", "hyperlocal-pages", "reports", "approvals", "agent-health"],
    ),
    _agent(
        "SEO-12", "Local & Area Page Agent", mode=_APPROVAL,
        description="Reviews money/area pages for local context, reviews, FAQs, "
        "LocalBusiness/Service schema and E-E-A-T signals across UAE/Qatar/Saudi and "
        "future GCC pages.",
        schedule="Weekly · Fri",
        required_inputs=["area_pages", "target_market"],
        allowed_actions=["audit_area_page", "suggest_local_signals"],
        forbidden_actions=["edit_pages"],
        human_approval_required=True,
        dashboard_sections=["hyperlocal-pages", "content-pipeline", "reports", "approvals", "agent-health"],
    ),
    _agent(
        "SEO-13", "Content Decay & Cannibalization Agent", mode=_MONITOR,
        description="Finds pages losing impressions/clicks/relevance and keyword-"
        "intent conflicts; recommends main vs weaker page and refresh/expand/merge/"
        "refocus.",
        schedule="Weekly · Mon",
        required_inputs=["gsc_property", "site_pages"],
        allowed_actions=["detect_decay", "detect_cannibalization", "recommend_action"],
        forbidden_actions=["edit_pages"],
        human_approval_required=True,
        dashboard_sections=["gsc-performance", "technical-seo", "reports", "agent-health"],
    ),
    _agent(
        "SEO-14", "AI Search Visibility Agent", mode=_MONITOR,
        description="Checks whether content is structured enough to appear in AI "
        "answers/overviews and improves direct answers, entities and extractable FAQ "
        "blocks. Does not invent facts.",
        schedule="Weekly · Tue",
        required_inputs=["site_pages"],
        allowed_actions=["assess_extractability", "suggest_structure"],
        forbidden_actions=["edit_pages", "invent_facts"],
        human_approval_required=True,
        dashboard_sections=["ai-search", "reports", "approvals", "agent-health"],
    ),
    _agent(
        "SEO-15", "GCC Expansion SEO Agent", mode=_MONITOR,
        description="Supports Saudi/Kuwait/Qatar/Bahrain/Oman expansion — suggests "
        "country-subfolder content, localized pages and market-specific "
        "opportunities from market config.",
        schedule="Weekly · Wed",
        required_inputs=["market_config", "target_service"],
        allowed_actions=["suggest_country_content", "suggest_localized_pages"],
        forbidden_actions=["publish_content"],
        human_approval_required=True,
        dashboard_sections=["hyperlocal-pages", "content-pipeline", "reports", "agent-health"],
    ),
    _agent(
        "SEO-16", "SEO Reporting Agent", mode=_MONITOR,
        description="Rolls every agent's output into a daily report (important "
        "changes, competitor updates, ranking movement, indexing issues, urgent "
        "first) and a weekly summary (wins, risks, priorities, next actions).",
        schedule="Daily · 18:00",
        required_inputs=[],
        allowed_actions=["generate_daily_report", "generate_weekly_report"],
        forbidden_actions=[],
        human_approval_required=False,
        status="Scheduled",
        dashboard_sections=["reports", "overview", "agent-health"],
    ),
]

_BY_ID = {a.id: a for a in _CATALOG}


def list_agents() -> list[SEOAgent]:
    """All 16 SEO agents, ordered SEO-01..SEO-16."""
    return list(_CATALOG)


def get_agent(agent_id: str) -> SEOAgent | None:
    return _BY_ID.get(agent_id)
