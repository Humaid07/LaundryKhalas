"""Routing simulator — rerun the SHARED engine with temporary overrides.

Ops can simulate "a driver goes offline", "a facility closes early / becomes busy
/ disables a service / changes rating / reaches capacity", "a driver shift starts /
ends / enters a break / becomes assigned", etc. Overrides are applied to an
in-memory copy of the loaded candidates — NO database edit — unless the caller
explicitly persists (Save Test Override, out of band). Same evaluator as production.
"""
from __future__ import annotations

import copy
from datetime import datetime

from services.routing import candidate_loader, evaluator
from services.routing.trial_facilities import DEFAULT_SEED_TIME

# Facility override keys that REPLACE the field value directly.
_FACILITY_SCALAR_KEYS = {
    "operating_status", "current_workload_pct", "rating", "review_count", "quality_score",
    "supports_express", "service_radius_km", "max_concurrent_orders", "active_load",
    "turnaround_hours", "accepts_orders", "is_active",
}


def apply_overrides(candidates: list[dict], overrides: dict | None) -> list[dict]:
    """Return a deep-copied candidate list with the overrides applied (pure)."""
    if not overrides:
        return candidates
    fac_ov = overrides.get("facilities") or {}
    drv_ov = overrides.get("drivers") or {}
    out: list[dict] = []
    for c in candidates:
        c2 = copy.deepcopy(c)
        fo = fac_ov.get(c2.get("code"))
        if fo:
            for k, v in fo.items():
                if k in _FACILITY_SCALAR_KEYS:
                    c2[k] = v
                elif k == "remove_services":
                    c2["service_codes"] = set(c2.get("service_codes") or set()) - set(v)
                elif k == "add_services":
                    c2["service_codes"] = set(c2.get("service_codes") or set()) | set(v)
                elif k == "remove_capabilities":
                    c2["capabilities"] = set(c2.get("capabilities") or set()) - set(v)
        for d in c2.get("drivers") or []:
            do = drv_ov.get(d.get("driver_code")) or drv_ov.get(d.get("code"))
            if do:
                for k, v in do.items():
                    d[k] = v
        out.append(c2)
    return out


async def simulate(request: dict, *, when: datetime | None = None,
                   overrides: dict | None = None, is_test: bool = True,
                   cost_approved: bool = False) -> dict:
    """Load the environment's candidates, apply overrides, and evaluate. No writes."""
    candidates = await candidate_loader.load_candidates(is_test=is_test, market=request.get("market"))
    patched = apply_overrides(candidates, overrides)
    when = when or DEFAULT_SEED_TIME
    result = evaluator.evaluate(patched, request, when, cost_approved=cost_approved)
    result["simulation_time"] = when.isoformat()
    result["candidate_count"] = len(patched)
    return result
