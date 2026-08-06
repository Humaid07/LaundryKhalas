"""Internal (ops) routing simulator + shadow-decision monitoring.

The simulator reruns the SHARED advanced engine with temporary overrides (no DB
edits); the monitoring endpoints expose the stored routing decisions, including the
legacy-vs-advanced shadow comparison. Guarded by ``deps.require_ops`` at include
time. Diagnostics are internal-only — never shown to customers or facilities.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Body, HTTPException

from db import database
from db.repositories import routing_decisions_repo
from services.routing import config as routing_config
from services.routing import simulator
from services.routing.trial_facilities import DEFAULT_SEED_TIME
from settings import get_settings

router = APIRouter(prefix="/api/internal/routing", tags=["routing"])


@router.get("/config")
async def routing_config_view():
    """Current routing mode + flags (read-only; mode is env-controlled for safety)."""
    s = get_settings()
    return {
        "enabled": bool(getattr(s, "advanced_routing_enabled", False)),
        "mode": routing_config.resolve_mode(s),
        "canary_percentage": int(getattr(s, "advanced_routing_canary_percentage", 0) or 0),
        "fallback_to_legacy": bool(getattr(s, "advanced_routing_fallback_to_legacy", True)),
        "require_snapshot": bool(getattr(s, "advanced_routing_require_decision_snapshot", True)),
        "routing_version": routing_config.ROUTING_VERSION,
        "test_facilities_enabled": bool(getattr(s, "enable_test_facilities", False)),
        "allow_test_facility_routing": bool(getattr(s, "allow_test_facility_routing", False)),
    }


@router.post("/simulate")
async def routing_simulate(body: dict = Body(...)):
    """Rerun routing for a hypothetical request with temporary overrides. Returns
    the full per-candidate explanation. No database edits."""
    if not database.is_supabase_mode():
        raise HTTPException(status_code=503, detail="Simulator requires DATABASE_MODE=supabase.")
    b = body or {}
    when = DEFAULT_SEED_TIME
    if b.get("when"):
        try:
            when = datetime.fromisoformat(str(b["when"]).replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid 'when' (use ISO 8601).")
    request = {
        "service_code": b.get("service_code"),
        "service_subtype": b.get("service_subtype"),
        "required_capabilities": b.get("required_capabilities") or [],
        "lat": b.get("lat"), "lon": b.get("lon"),
        "area": b.get("area"), "city": b.get("city"), "emirate": b.get("emirate"),
        "market": b.get("market"),
        "priority": (b.get("priority") or "standard"),
        "required_turnaround_hours": b.get("required_turnaround_hours"),
        "is_test": bool(b.get("is_test", True)),
    }
    result = await simulator.simulate(
        request, when=when, overrides=b.get("overrides"),
        is_test=request["is_test"], cost_approved=bool(b.get("cost_approved")))

    if b.get("save"):  # persist as a simulator decision (test-marked)
        await routing_decisions_repo.create(
            order_uuid=None, order_ref=b.get("order_ref"),
            environment=("TEST" if request["is_test"] else "production"),
            routing_mode="simulator", routing_version=routing_config.ROUTING_VERSION,
            result=result, request=request, simulation_time=when,
            advanced_selected_facility_id=result.get("selected_facility_id"),
            created_by="ops_simulator", is_test_data=request["is_test"])
    return result


@router.get("/decisions")
async def routing_decisions(environment: str | None = None, limit: int = 50):
    if not database.is_supabase_mode():
        return []
    return await routing_decisions_repo.list_recent(environment=environment, limit=min(int(limit), 200))


@router.get("/decisions/mismatches")
async def routing_mismatches(limit: int = 50):
    """Shadow-mode decisions where legacy and advanced selected DIFFERENT facilities
    — the queue Operations reviews before enabling canary/live."""
    if not database.is_supabase_mode():
        return []
    return await routing_decisions_repo.list_mismatches(limit=min(int(limit), 200))
