"""LaundryKhalas SEO Agents — Phase 1 foundation (mock-first, approval-gated).

This package is a self-contained SEO agent system that runs INSIDE the active
FastAPI backend but is fully isolated from the WhatsApp/Evolution work:

  * No Supabase tables/migrations — state lives in an in-memory store
    (``store.py``) seeded deterministically at import. This keeps the live
    dev/test Supabase schema and the Evolution auto-reply flow untouched.
  * No live web/Google/LinkedIn/GSC/Ahrefs/Semrush calls — every runner reads
    deterministic mock sources (``mock_sources.py``).
  * SEO agents ONLY research, monitor, draft, and recommend. Every action that
    would change a page, submit a URL, publish content, or start outreach
    becomes an approval task (``approvals.py``) — never an autonomous action.

Public surface is the API router in ``api/seo_agents.py``; everything the
dashboard shows comes from here (no backend-only invisible agents).
"""
from seo_agents import catalog, reports, runner, store  # noqa: F401

__all__ = ["catalog", "runner", "reports", "store"]
