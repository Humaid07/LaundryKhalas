"""Driver availability model (pure, deterministic, time-aware).

Derives a driver's canonical availability status at a given evaluation time from
shift / break / leave / employment / stored-status / active-assignment data. This
is the single source of truth for the routing engine's "available_driver_count" —
a facility with three drivers but zero AVAILABLE ones must never be treated as
more available than a facility with one genuinely available driver.

Pure over dicts (accepts datetime.time / datetime OR their string forms), so the
whole model is unit-testable without a DB or wall-clock.
"""

from __future__ import annotations

from datetime import datetime, time

# Canonical availability taxonomy.
AVAILABLE = "AVAILABLE"
ASSIGNED = "ASSIGNED"
ON_PICKUP = "ON_PICKUP"
ON_DELIVERY = "ON_DELIVERY"
ON_BREAK = "ON_BREAK"
OFFLINE = "OFFLINE"
ON_LEAVE = "ON_LEAVE"
NOT_YET_ON_SHIFT = "NOT_YET_ON_SHIFT"
SHIFT_ENDED = "SHIFT_ENDED"
UNAVAILABLE = "UNAVAILABLE"

# availability status -> routing rejection reason code.
STATUS_REASON = {
    OFFLINE: "DRIVER_OFFLINE",
    ON_LEAVE: "DRIVER_ON_LEAVE",
    ON_BREAK: "DRIVER_ON_BREAK",
    NOT_YET_ON_SHIFT: "DRIVER_OUTSIDE_SHIFT",
    SHIFT_ENDED: "DRIVER_OUTSIDE_SHIFT",
    ASSIGNED: "DRIVER_ASSIGNMENT_LIMIT_REACHED",
    ON_PICKUP: "DRIVER_ASSIGNMENT_LIMIT_REACHED",
    ON_DELIVERY: "DRIVER_ASSIGNMENT_LIMIT_REACHED",
    UNAVAILABLE: "NO_AVAILABLE_DRIVER",
}

_ACTIVE_TASK_STATUS = {
    "pickup_in_progress": ON_PICKUP,
    "delivery_in_progress": ON_DELIVERY,
    "assigned": ASSIGNED,
    "on_job": ASSIGNED,
    "handoff_in_progress": ASSIGNED,
}


def _as_time(v) -> time | None:
    if v is None or isinstance(v, time):
        return v
    if isinstance(v, datetime):
        return v.time()
    s = str(v).strip()
    if not s:
        return None
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(s, fmt).time()
        except ValueError:
            continue
    return None


def _as_dt(v) -> datetime | None:
    if v is None or isinstance(v, datetime):
        return v
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None


def _within_time(t: time, start: time | None, end: time | None) -> bool:
    """t inside [start, end] (inclusive). Handles an overnight window (end<start)."""
    if start is None or end is None:
        return False
    if start <= end:
        return start <= t <= end
    return t >= start or t <= end  # overnight


def _mapped_day(when: datetime) -> int:
    # python Mon=0..Sun=6 -> 0=Sun..6=Sat (matches facility_timings.day_of_week)
    return (when.weekday() + 1) % 7


def _on_shift(driver: dict, when: datetime) -> str | None:
    """None when on shift; else NOT_YET_ON_SHIFT / SHIFT_ENDED (outside window /
    not scheduled today)."""
    days = driver.get("service_days")
    if days is not None:
        try:
            allowed = {int(d) for d in days}
        except (TypeError, ValueError):
            allowed = set()
        if allowed and _mapped_day(when) not in allowed:
            return SHIFT_ENDED  # not scheduled this day
    start = _as_time(driver.get("shift_start"))
    end = _as_time(driver.get("shift_end"))
    if start is None or end is None:
        return None  # no shift configured -> don't over-block
    t = when.time()
    if _within_time(t, start, end):
        return None
    # Distinguish "before shift" from "after shift" for the same-day case.
    if start <= end and t < start:
        return NOT_YET_ON_SHIFT
    return SHIFT_ENDED


def compute_driver_availability(
    driver: dict, when: datetime, *, active_assignment_count: int | None = None,
) -> dict:
    """Return {status, available, express_available, reason} for one driver at
    ``when``. ``active_assignment_count`` overrides driver['active_assignment_count']
    (number of currently-active assignments) when provided."""
    status = (driver.get("status") or "").lower()
    employment = (driver.get("employment_status") or "active").lower()
    express_eligible = bool(driver.get("express_eligible"))

    def out(s: str) -> dict:
        avail = s == AVAILABLE
        return {
            "status": s,
            "available": avail,
            "express_available": avail and express_eligible,
            "express_eligible": express_eligible,
            "reason": None if avail else STATUS_REASON.get(s, "NO_AVAILABLE_DRIVER"),
        }

    # 1. Offline / inactive.
    if not driver.get("active", True) or status == "offline" or employment == "inactive":
        return out(OFFLINE)

    # 2. On leave (stored status, employment, or an explicit leave window).
    leave_start, leave_end = _as_dt(driver.get("leave_start")), _as_dt(driver.get("leave_end"))
    if (status == "on_leave" or employment == "on_leave"
            or (leave_start and leave_end and leave_start <= when <= leave_end)):
        return out(ON_LEAVE)

    # 3. Explicit availability window (available_from/until), if set.
    af, au = _as_dt(driver.get("available_from")), _as_dt(driver.get("available_until"))
    if af and when < af:
        return out(NOT_YET_ON_SHIFT)
    if au and when > au:
        return out(SHIFT_ENDED)

    # 4. Outside shift / not scheduled today.
    shift = _on_shift(driver, when)
    if shift is not None:
        return out(shift)

    # 5. On break (stored status or break window covers ``when``).
    if status == "on_break" or _within_time(when.time(), _as_time(driver.get("break_start")),
                                            _as_time(driver.get("break_end"))):
        return out(ON_BREAK)

    if status == "issue_reported":
        return out(UNAVAILABLE)

    # 6. Busy by stored status (assigned / on a pickup / delivery / handoff).
    if status in _ACTIVE_TASK_STATUS:
        return out(_ACTIVE_TASK_STATUS[status])

    # 7. At the assignment limit (a "free" driver that already holds max tasks).
    count = active_assignment_count if active_assignment_count is not None \
        else int(driver.get("active_assignment_count") or 0)
    if count >= int(driver.get("max_concurrent_assignments") or 1):
        return out(ASSIGNED)

    # 8. Available.
    return out(AVAILABLE)


def summarize_drivers(driver_avail: list[dict]) -> dict:
    """Facility-level driver-availability breakdown from per-driver results.

    ``driver_avail`` is a list of compute_driver_availability(...) dicts; each may
    also carry ``scheduled`` (bool) and ``online`` (bool) hints (defaults derived
    from status)."""
    counts = {
        "total": len(driver_avail), "scheduled": 0, "online": 0, "available": 0,
        "on_break": 0, "on_leave": 0, "assigned": 0, "outside_shift": 0,
        "offline": 0, "express_available": 0,
    }
    for d in driver_avail:
        s = d.get("status")
        if s not in (SHIFT_ENDED, NOT_YET_ON_SHIFT, ON_LEAVE, OFFLINE):
            counts["scheduled"] += 1
        if s not in (OFFLINE, ON_LEAVE):
            counts["online"] += 1
        if d.get("available"):
            counts["available"] += 1
        if d.get("express_available"):
            counts["express_available"] += 1
        if s == ON_BREAK:
            counts["on_break"] += 1
        elif s == ON_LEAVE:
            counts["on_leave"] += 1
        elif s in (ASSIGNED, ON_PICKUP, ON_DELIVERY):
            counts["assigned"] += 1
        elif s in (NOT_YET_ON_SHIFT, SHIFT_ENDED):
            counts["outside_shift"] += 1
        elif s == OFFLINE:
            counts["offline"] += 1
    return counts
