"""Facility eligibility + matching for order routing and agent tools.

Given a service + optional customer location/time, returns the facilities that can
actually take the work, ranked best-first. This is the DB-backed, grounded engine
behind ``find_eligible_facilities`` (agent tool) — no data is invented.

Rules (CLAUDE.md §4/§9):
  * ``closed`` / ``paused`` facilities are never eligible; ``busy`` is eligible but
    ranked below ``open``.
  * a facility must OFFER the requested service (facility_services, category level).
  * if coordinates are known on both sides, a facility outside its
    ``service_radius_km`` is excluded; distance is a ranking key otherwise.
  * if a time is given, the facility must be open that weekday (facility_timings).
  * ``quality_score`` is used only for INTERNAL ranking and is NEVER returned in the
    safe output (privacy firewall §7). Internal rates are never touched here.

A short in-process TTL cache avoids re-reading every facility on each call;
``invalidate()`` is called by every facility mutation so the agent never reads
stale availability.
"""
from __future__ import annotations

import time

from db import database
from services.facility_pricing import haversine_km

# Order lanes that still occupy a facility's capacity (mirrors facilities_repo).
_ACTIVE_LOAD_STATUSES = ("active", "pickup_scheduled", "picked_up", "in_cleaning",
                         "ready_for_delivery", "out_for_delivery")
_UNAVAILABLE_STATUSES = ("closed", "paused")

_TTL_SECONDS = 30.0
_cache: dict = {"at": -1.0, "data": None}


def invalidate() -> None:
    """Drop the cached facility snapshot (called after any facility mutation)."""
    _cache["at"] = -1.0
    _cache["data"] = None


async def _load() -> list[dict]:
    now = time.monotonic()
    if _cache["data"] is not None and (now - _cache["at"]) < _TTL_SECONDS:
        return _cache["data"]

    facilities = await database.fetch(
        "select id, code, name, area, city, emirate, latitude, longitude, "
        "service_radius_km, capacity_daily, capacity_unit, operating_status, "
        "accepts_orders, quality_score, created_at "
        "from facilities where is_active = true"
    )
    svc_rows = await database.fetch(
        "select facility_id, service_code from facility_services where offered = true"
    )
    load_rows = await database.fetch(
        "select facility_id, count(*) as c from orders where status = any($1::text[]) "
        "group by facility_id",
        list(_ACTIVE_LOAD_STATUSES),
    )
    timing_rows = await database.fetch(
        "select facility_id, day_of_week, opens_at, closes_at, is_closed, is_24h "
        "from facility_timings"
    )

    svc_map: dict = {}
    for r in svc_rows:
        svc_map.setdefault(str(r["facility_id"]), set()).add(r["service_code"])
    load_map = {str(r["facility_id"]): r["c"] for r in load_rows}
    timing_map: dict = {}
    for r in timing_rows:
        timing_map.setdefault(str(r["facility_id"]), {})[r["day_of_week"]] = dict(r)

    enriched = []
    for f in facilities:
        fid = str(f["id"])
        d = dict(f)
        d["id"] = fid
        d["service_codes"] = svc_map.get(fid, set())
        d["active_load"] = load_map.get(fid, 0)
        d["timings"] = timing_map.get(fid, {})
        enriched.append(d)

    _cache["data"] = enriched
    _cache["at"] = now
    return enriched


def _has_spare_capacity(fac: dict) -> bool:
    cap = fac.get("capacity_daily")
    return cap is None or fac.get("active_load", 0) < cap


def _open_at(fac: dict, day: int | None, t) -> bool:
    """True if the facility is open on ``day`` (0=Sun..6=Sat) at time ``t``. When no
    timing row is configured for the day, assume available (don't over-block)."""
    if day is None:
        return True
    row = fac.get("timings", {}).get(day)
    if row is None:
        return True
    if row.get("is_closed"):
        return False
    if row.get("is_24h"):
        return True
    opens, closes = row.get("opens_at"), row.get("closes_at")
    if opens is None or closes is None or t is None:
        return True
    return opens <= t <= closes


def _to_safe(fac: dict, dist) -> dict:
    """Customer/agent-safe facility dict — NO quality_score, NO rates."""
    return {
        "id": fac["id"],
        "code": fac.get("code"),
        "name": fac.get("name"),
        "area": fac.get("area"),
        "city": fac.get("city"),
        "emirate": fac.get("emirate"),
        "operating_status": fac.get("operating_status"),
        "distance_km": dist,
        "capacity_daily": fac.get("capacity_daily"),
        "capacity_unit": fac.get("capacity_unit"),
        "has_spare_capacity": _has_spare_capacity(fac),
    }


def rank(
    facilities: list[dict],
    *,
    service_code: str | None = None,
    lat=None,
    lon=None,
    when=None,
    limit: int = 5,
) -> list[dict]:
    """Pure eligibility filter + ranking over already-loaded facility dicts.

    Each facility dict may carry ``service_codes`` (set), ``active_load`` (int),
    ``timings`` (dict keyed by day_of_week), plus the facility columns. ``when`` is
    an optional datetime for the operating-hours check.
    """
    day = None
    t = None
    if when is not None:
        day = (when.weekday() + 1) % 7  # python Mon=0..Sun=6 -> 0=Sun..6=Sat
        t = when.time()

    eligible: list[tuple] = []
    for fac in facilities:
        if fac.get("operating_status") in _UNAVAILABLE_STATUSES:
            continue
        if not fac.get("accepts_orders", True):
            continue
        if service_code and service_code not in fac.get("service_codes", set()):
            continue
        dist = haversine_km(lat, lon, fac.get("latitude"), fac.get("longitude"))
        radius = fac.get("service_radius_km")
        if dist is not None and radius is not None and dist > float(radius):
            continue
        if not _open_at(fac, day, t):
            continue
        eligible.append((fac, dist))

    def sort_key(item):
        fac, dist = item
        quality = fac.get("quality_score")
        quality = float(quality) if quality is not None else -1.0
        return (
            0 if fac.get("operating_status") == "open" else 1,   # open first
            0 if _has_spare_capacity(fac) else 1,                # spare capacity first
            dist if dist is not None else float("inf"),          # nearest first
            -quality,                                            # higher quality first
            str(fac.get("created_at") or ""),                    # stable tie-break
        )

    eligible.sort(key=sort_key)
    return [_to_safe(fac, dist) for fac, dist in eligible[:limit]]


async def find_eligible(
    *,
    service_code: str | None = None,
    lat=None,
    lon=None,
    when=None,
    limit: int = 5,
) -> list[dict]:
    """Load facilities (cached) and return the ranked, safe eligibility list."""
    facilities = await _load()
    return rank(facilities, service_code=service_code, lat=lat, lon=lon,
                when=when, limit=limit)
