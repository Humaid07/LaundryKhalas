"""Environment-isolated candidate loaders (asyncpg / Supabase).

Builds the candidate dicts (facility + offered services + express flags +
specialist capabilities + timings + drivers with availability fields + live load)
that the shared pure evaluator consumes. The `is_test` flag selects EXACTLY ONE
population: a production order loads only production facilities/drivers, a test
order loads only test facilities/drivers — enforced in SQL (`is_test_facility`,
`is_test_driver`) so the two can never mix.
"""
from __future__ import annotations

from db import database

# Order lanes that still occupy a facility's capacity.
_ACTIVE_LOAD_STATUSES = ("active", "pickup_scheduled", "picked_up", "in_cleaning",
                         "ready_for_delivery", "out_for_delivery")
# Driver-assignment statuses that count against a driver's assignment limit.
_ACTIVE_ASSIGNMENT_STATUSES = ("assigned", "in_progress")

_FAC_COLS = (
    "id, code, name, area, city, emirate, latitude, longitude, service_radius_km, "
    "capacity_daily, max_concurrent_orders, current_workload_pct, capacity_unit, "
    "operating_status, accepts_orders, is_active, quality_score, rating, review_count, "
    "supports_express, turnaround_hours, market, is_test_facility, created_at"
)
_DRV_COLS = (
    "id, facility_id, name, driver_code, active, status, employment_status, "
    "shift_start, shift_end, break_start, break_end, service_days, express_eligible, "
    "max_concurrent_assignments, leave_start, leave_end, available_from, available_until, "
    "is_test_driver"
)


async def load_candidates(*, is_test: bool, market: str | None = None) -> list[dict]:
    """Load the candidate facilities (+ drivers) for the given environment.

    ONLY facilities with `is_test_facility = is_test` are returned; drivers are
    matched the same way, so a production order can never see a test facility or a
    test driver (and vice-versa)."""
    facilities = await database.fetch(
        f"select {_FAC_COLS} from facilities where is_active = true and is_test_facility = $1",
        is_test,
    )
    if not facilities:
        return []
    fac_ids = [str(f["id"]) for f in facilities]

    svc_rows = await database.fetch(
        "select facility_id, service_code, express_ok from facility_services "
        "where offered = true and facility_id = any($1::uuid[])", fac_ids)
    cap_rows = await database.fetch(
        "select facility_id, capability_code from facility_capabilities "
        "where facility_id = any($1::uuid[])", fac_ids)
    timing_rows = await database.fetch(
        "select facility_id, day_of_week, opens_at, closes_at, is_closed, is_24h "
        "from facility_timings where facility_id = any($1::uuid[])", fac_ids)
    load_rows = await database.fetch(
        "select facility_id, count(*) as c from orders where status = any($1::text[]) "
        "and facility_id = any($2::uuid[]) group by facility_id",
        list(_ACTIVE_LOAD_STATUSES), fac_ids)
    driver_rows = await database.fetch(
        f"select {_DRV_COLS} from facility_drivers "
        "where facility_id = any($1::uuid[]) and is_test_driver = $2", fac_ids, is_test)
    assign_rows = await database.fetch(
        "select driver_id, count(*) as c from driver_assignments "
        "where status = any($1::text[]) group by driver_id",
        list(_ACTIVE_ASSIGNMENT_STATUSES))

    svc_map: dict[str, set] = {}
    express_map: dict[str, set] = {}
    for r in svc_rows:
        fid = str(r["facility_id"])
        svc_map.setdefault(fid, set()).add(r["service_code"])
        if r["express_ok"]:
            express_map.setdefault(fid, set()).add(r["service_code"])
    cap_map: dict[str, set] = {}
    for r in cap_rows:
        cap_map.setdefault(str(r["facility_id"]), set()).add(r["capability_code"])
    timing_map: dict[str, dict] = {}
    for r in timing_rows:
        timing_map.setdefault(str(r["facility_id"]), {})[r["day_of_week"]] = dict(r)
    load_map = {str(r["facility_id"]): r["c"] for r in load_rows}
    assign_map = {str(r["driver_id"]): r["c"] for r in assign_rows}
    drivers_by_fac: dict[str, list] = {}
    for r in driver_rows:
        d = dict(r)
        d["id"] = str(r["id"])
        d["active_assignment_count"] = int(assign_map.get(str(r["id"]), 0))
        drivers_by_fac.setdefault(str(r["facility_id"]), []).append(d)

    candidates = []
    for f in facilities:
        fid = str(f["id"])
        c = dict(f)
        c["id"] = fid
        c["service_codes"] = svc_map.get(fid, set())
        c["express_service_codes"] = express_map.get(fid, set())
        c["capabilities"] = cap_map.get(fid, set())
        c["timings"] = timing_map.get(fid, {})
        c["active_load"] = load_map.get(fid, 0)
        c["drivers"] = drivers_by_fac.get(fid, [])
        candidates.append(c)
    return candidates
