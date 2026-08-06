"""Hard eligibility checks (pure). Runs BEFORE scoring — a facility that fails any
hard requirement is rejected with reason codes and never enters ranking.

Operates over a "candidate" dict (facility + its offered services, capabilities,
timings, and driver list) and a "request" dict (service, location, time, priority,
required capabilities, turnaround, environment). Driver availability is derived by
services.routing.availability at the requested time.
"""

from __future__ import annotations

from datetime import datetime

from services.facility_pricing import haversine_km
from services.routing import availability as av

_UNAVAILABLE_STATUSES = {"closed": "FACILITY_CLOSED", "paused": "FACILITY_PAUSED"}


def _facility_open(candidate: dict, when: datetime | None) -> bool:
    if when is None:
        return True
    day = (when.weekday() + 1) % 7  # 0=Sun..6=Sat
    timings = candidate.get("timings") or {}
    row = timings.get(day)
    if row is None:
        return True  # no timing configured -> don't over-block
    if row.get("is_closed"):
        return False
    if row.get("is_24h"):
        return True
    opens, closes = av._as_time(row.get("opens_at")), av._as_time(row.get("closes_at"))
    if opens is None or closes is None:
        return True
    return av._within_time(when.time(), opens, closes)


def _remaining_capacity(candidate: dict) -> float | None:
    """Remaining standard capacity, or None when unlimited. Uses the test/override
    workload % when present, else max_concurrent_orders/capacity_daily vs live load."""
    wl = candidate.get("current_workload_pct")
    if wl is not None:
        return max(0.0, 100.0 - float(wl))  # percent-remaining
    cap = candidate.get("max_concurrent_orders")
    if cap is None:
        cap = candidate.get("capacity_daily")
    if cap is None:
        return None
    return float(cap) - float(candidate.get("active_load", 0) or 0)


def driver_availability(candidate: dict, when: datetime) -> list[dict]:
    """Per-driver availability results at ``when`` for this candidate's drivers."""
    out = []
    for d in (candidate.get("drivers") or []):
        out.append(av.compute_driver_availability(d, when))
    return out


def evaluate_candidate(candidate: dict, request: dict, when: datetime) -> dict:
    """Return the full eligibility breakdown for one candidate. ``eligible`` is True
    only when NO hard rejection reason applies."""
    reasons: list[str] = []
    is_test_req = bool(request.get("is_test"))

    # 1. Environment isolation (defence-in-depth; the loader already filters).
    if bool(candidate.get("is_test_facility")) != is_test_req:
        reasons.append("TEST_ENVIRONMENT_MISMATCH")

    # 2. Status.
    status = (candidate.get("operating_status") or "").lower()
    if status in _UNAVAILABLE_STATUSES:
        reasons.append(_UNAVAILABLE_STATUSES[status])
    if not candidate.get("is_active", True) or not candidate.get("accepts_orders", True):
        reasons.append("FACILITY_PAUSED")

    # 3. Service coverage.
    service = request.get("service_code")
    service_codes = candidate.get("service_codes") or set()
    if service and service not in service_codes:
        reasons.append("SERVICE_NOT_SUPPORTED")

    # 4. Specialist capabilities.
    required_caps = set(request.get("required_capabilities") or [])
    caps = candidate.get("capabilities") or set()
    if required_caps and not required_caps.issubset(caps):
        reasons.append("SPECIALIST_CAPABILITY_MISSING")

    # 5. Service radius / distance.
    dist = haversine_km(request.get("lat"), request.get("lon"),
                        candidate.get("latitude"), candidate.get("longitude"))
    radius = candidate.get("service_radius_km")
    if dist is not None and radius is not None and dist > float(radius):
        reasons.append("OUTSIDE_SERVICE_RADIUS")

    # 6. Market / emirate.
    req_market = request.get("market")
    fac_market = candidate.get("market")
    if req_market and fac_market and str(req_market).lower() != str(fac_market).lower():
        reasons.append("MARKET_NOT_SUPPORTED")

    # 7. Operating hours.
    is_open = _facility_open(candidate, when)
    if not is_open:
        reasons.append("FACILITY_OUTSIDE_WORKING_HOURS")

    # 8. Capacity.
    remaining = _remaining_capacity(candidate)
    if remaining is not None and remaining <= 0:
        reasons.append("CAPACITY_UNAVAILABLE")

    # 9. Turnaround.
    req_turn = request.get("required_turnaround_hours")
    fac_turn = candidate.get("turnaround_hours")
    if req_turn is not None and fac_turn is not None and float(fac_turn) > float(req_turn):
        reasons.append("TURNAROUND_UNAVAILABLE")

    # 10. Drivers + availability.
    drivers = candidate.get("drivers") or []
    driver_avail = driver_availability(candidate, when)
    summary = av.summarize_drivers(driver_avail)
    express_requested = (request.get("priority") or "standard").lower() == "express"

    if len(drivers) == 0:
        reasons.append("NO_DRIVERS_ASSIGNED")
    else:
        if summary["scheduled"] == 0:
            reasons.append("NO_DRIVERS_SCHEDULED")
        if summary["available"] == 0:
            reasons.append("NO_AVAILABLE_DRIVER")
            # Surface the SPECIFIC per-driver reasons too (DRIVER_ON_BREAK,
            # DRIVER_OUTSIDE_SHIFT, DRIVER_ON_LEAVE, DRIVER_OFFLINE,
            # DRIVER_ASSIGNMENT_LIMIT_REACHED) for the routing explanation.
            for r in driver_avail:
                if not r.get("available") and r.get("reason"):
                    reasons.append(r["reason"])

    # 11. Express.
    if express_requested:
        express_service_codes = candidate.get("express_service_codes") or set()
        supports_express = bool(candidate.get("supports_express")) and (
            not service or service in express_service_codes)
        if not supports_express:
            reasons.append("EXPRESS_NOT_SUPPORTED")
        elif summary["express_available"] == 0:
            reasons.append("NO_EXPRESS_DRIVER_AVAILABLE")

    # De-dup while preserving order.
    seen: set[str] = set()
    rejection_reasons = [r for r in reasons if not (r in seen or seen.add(r))]

    return {
        "facility_id": candidate.get("id"),
        "facility_code": candidate.get("code"),
        "facility_name": candidate.get("name"),
        "eligible": len(rejection_reasons) == 0,
        "rejection_reasons": rejection_reasons,
        "distance_km": dist,
        "service_supported": not service or service in service_codes,
        "specialist_supported": not required_caps or required_caps.issubset(caps),
        "inside_radius": not (dist is not None and radius is not None and dist > float(radius)),
        "facility_open": is_open,
        "remaining_capacity": remaining,
        "driver_summary": summary,
        "driver_availability": driver_avail,
        "express_requested": express_requested,
    }
