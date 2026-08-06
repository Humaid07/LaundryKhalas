"""Valid pickup-slot calculation (pure). A slot is valid only when the facility is
open, at least one eligible driver is available during it, the lead time is met,
and Express cutoff rules are satisfied. Slot ids are STABLE (hash of facility +
start), so retries of the same evaluation reference the same slot — Claude never
invents a pickup time.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

from services.routing import availability as av
from services.routing.eligibility import _facility_open

DEFAULT_STEP_MINUTES = 30
DEFAULT_SLOT_MINUTES = 120
DEFAULT_HORIZON_HOURS = 12
EXPRESS_CUTOFF_HOUR = 15  # 3 PM — Express must be requested before this, same day.


def _slot_id(facility_id, start: datetime) -> str:
    return "slot_" + hashlib.sha1(f"{facility_id}|{start.isoformat()}".encode()).hexdigest()[:16]


def _driver_available_at(candidate: dict, t: datetime, *, express: bool) -> bool:
    for d in (candidate.get("drivers") or []):
        r = av.compute_driver_availability(d, t)
        if r["available"] and (not express or r["express_available"]):
            return True
    return False


def earliest_slot(
    candidate: dict,
    request: dict,
    when: datetime,
    *,
    express: bool | None = None,
    step_minutes: int = DEFAULT_STEP_MINUTES,
    slot_minutes: int = DEFAULT_SLOT_MINUTES,
    horizon_hours: int = DEFAULT_HORIZON_HOURS,
    express_cutoff_hour: int = EXPRESS_CUTOFF_HOUR,
) -> dict | None:
    """First valid pickup slot at/after ``when`` for this candidate, or None.

    Scans in ``step_minutes`` increments up to ``horizon_hours``. For Express, the
    slot must start before the same-day cutoff AND have an Express-capable driver
    available."""
    if express is None:
        express = (request.get("priority") or "standard").lower() == "express"
    steps = int(horizon_hours * 60 / step_minutes)
    t = when
    for _ in range(steps + 1):
        if express and (t.date() == when.date()) and t.hour >= express_cutoff_hour:
            # same-day express after cutoff is not auto-confirmable
            t = t + timedelta(minutes=step_minutes)
            continue
        end = t + timedelta(minutes=slot_minutes)
        if _facility_open(candidate, t) and _facility_open(candidate, end - timedelta(minutes=1)) \
                and _driver_available_at(candidate, t, express=express):
            delay = (t - when).total_seconds() / 60.0
            return {
                "id": _slot_id(candidate.get("id"), t),
                "start": t.isoformat(),
                "end": end.isoformat(),
                "express": express,
                "delay_minutes": round(delay, 1),
            }
        t = t + timedelta(minutes=step_minutes)
    return None


def express_slot_available(when: datetime, *, express_cutoff_hour: int = EXPRESS_CUTOFF_HOUR) -> bool:
    """Whether an Express same-day pickup is allowed at ``when`` (before cutoff)."""
    return when.hour < express_cutoff_hour
