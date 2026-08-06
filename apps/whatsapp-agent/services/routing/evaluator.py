"""Shared advanced routing evaluator (pure).

Orchestrates hard eligibility -> pickup slot -> scoring -> ranking -> explanation
over already-loaded candidate dicts, and returns the shared result contract used
by BOTH the production routing flow and the test simulator. No DB, no wall-clock,
no invented facilities/drivers/slots.
"""

from __future__ import annotations

from datetime import datetime

from services.routing import availability as av
from services.routing import eligibility as elig_mod
from services.routing import scoring as scoring_mod
from services.routing import slots as slots_mod
from services.routing.config import ROUTING_VERSION


def _pick_driver(candidate: dict, when: datetime, express: bool) -> str | None:
    for d in (candidate.get("drivers") or []):
        r = av.compute_driver_availability(d, when)
        if r["available"] and (not express or r["express_available"]):
            return str(d.get("id") or d.get("driver_code"))
    return None


def _candidate_breakdown(candidate: dict, elig: dict, when: datetime, *, cost_approved: bool) -> dict:
    """Full per-candidate explanation row (eligible OR rejected)."""
    summary = elig["driver_summary"]
    express = elig["express_requested"]
    row = {
        "facility_id": elig["facility_id"],
        "facility_code": elig["facility_code"],
        "facility_name": elig["facility_name"],
        "distance_km": elig["distance_km"],
        "service_supported": elig["service_supported"],
        "specialist_supported": elig["specialist_supported"],
        "facility_open": elig["facility_open"],
        "inside_radius": elig["inside_radius"],
        "rating": candidate.get("rating"),
        "review_count": candidate.get("review_count"),
        "quality_score": candidate.get("quality_score"),
        "operating_status": candidate.get("operating_status"),
        "remaining_capacity": elig["remaining_capacity"],
        "max_capacity": candidate.get("max_concurrent_orders") or candidate.get("capacity_daily"),
        "current_workload_pct": candidate.get("current_workload_pct"),
        "turnaround_hours": candidate.get("turnaround_hours"),
        # driver breakdown — total vs the real availability sub-counts.
        "total_drivers": summary["total"],
        "drivers_scheduled": summary["scheduled"],
        "drivers_online": summary["online"],
        "drivers_available": summary["available"],
        "drivers_on_break": summary["on_break"],
        "drivers_on_leave": summary["on_leave"],
        "drivers_assigned": summary["assigned"],
        "drivers_outside_shift": summary["outside_shift"],
        "express_drivers_available": summary["express_available"],
        "express_requested": express,
        "eligible": elig["eligible"],
        "rejection_reasons": elig["rejection_reasons"],
    }
    if elig["eligible"]:
        slot = slots_mod.earliest_slot(candidate, {"priority": "express" if express else "standard"}, when, express=express)
        if slot is None:
            # eligible now but no confirmable slot (e.g. express after cutoff) -> reject.
            row["eligible"] = False
            row["rejection_reasons"] = (elig["rejection_reasons"] or []) + (
                ["NO_EXPRESS_DRIVER_AVAILABLE"] if express else ["NO_AVAILABLE_DRIVER"])
            row["earliest_pickup_slot"] = None
            return row
        score = scoring_mod.score_candidate(elig, candidate, pickup_delay_minutes=slot["delay_minutes"], cost_approved=cost_approved)
        row["earliest_pickup_slot"] = slot
        row["weighted_rating"] = score["weighted_rating_value"]
        row["score"] = score["score"]
        row["score_components"] = score["components"]
        row["selected_driver_id"] = _pick_driver(candidate, when, express)
    else:
        row["earliest_pickup_slot"] = None
        row["score"] = None
    return row


def evaluate(candidates: list[dict], request: dict, when: datetime, *, cost_approved: bool = False) -> dict:
    """Evaluate candidates for a routing request and return the result contract."""
    express = (request.get("priority") or "standard").lower() == "express"
    eligible: list[dict] = []
    rejected: list[dict] = []
    for c in candidates:
        elig = elig_mod.evaluate_candidate(c, request, when)
        row = _candidate_breakdown(c, elig, when, cost_approved=cost_approved)
        (eligible if row["eligible"] else rejected).append(row)

    def sort_key(r):
        return (
            -(r.get("score") or 0.0),
            r["distance_km"] if r.get("distance_km") is not None else float("inf"),
            -(r.get("weighted_rating") or 0.0),
            str(r.get("facility_code") or ""),
        )

    eligible.sort(key=sort_key)

    selected = eligible[0] if eligible else None
    if selected:
        slot = selected.get("earliest_pickup_slot") or {}
        reason = (
            f"Highest-scoring eligible facility: matching service, "
            f"{selected['drivers_available']} available driver(s), "
            f"{selected['distance_km']}km, weighted rating {selected.get('weighted_rating')}."
        )
        result = {
            "selected_facility_id": selected["facility_id"],
            "selected_driver_id": selected.get("selected_driver_id"),
            "selected_pickup_slot_id": slot.get("id"),
            "score_components": selected.get("score_components"),
            "selection_reason": reason,
        }
    else:
        result = {
            "selected_facility_id": None,
            "selected_driver_id": None,
            "selected_pickup_slot_id": None,
            "score_components": None,
            "selection_reason": "No eligible facility — route to Operations manual-routing.",
        }

    result.update({
        "routing_version": ROUTING_VERSION,
        "eligible_candidates": eligible,
        "rejected_candidates": rejected,
        "eligible_count": len(eligible),
        "rejected_count": len(rejected),
        "fallback_used": False,
    })
    return result
