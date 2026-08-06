"""Idempotent seed of the 11 trial (TEST) facilities + drivers into dev/test Supabase.

Source of truth: services/routing/trial_facilities.py. Running repeatedly UPDATES the
same rows (upsert by facility code / driver code) — never duplicates. Every row is
TEST-only (is_test_facility / is_test_driver / environment=TEST) so production
routing never sees them.

GUARDS (all required): DATABASE_MODE=supabase, database_env=test,
ENABLE_TEST_FACILITIES=true, ALLOW_TEST_SEED=true.

Usage (from apps/whatsapp-agent):
    ENABLE_TEST_FACILITIES=true ALLOW_TEST_SEED=true \
      ./.venv/Scripts/python.exe scripts/seed_test_facilities_and_drivers.py
"""
from __future__ import annotations

import asyncio
import pathlib
import sys
from datetime import datetime

import asyncpg


def _pt(s):
    """'HH:MM' -> datetime.time (asyncpg needs a time object, not a string)."""
    return datetime.strptime(s, "%H:%M").time() if s else None

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from settings import get_settings  # noqa: E402
from services.routing.trial_facilities import TRIAL_FACILITIES  # noqa: E402


def _dsn() -> str:
    s = get_settings()
    if (s.database_mode or "").lower() != "supabase":
        raise SystemExit(f"Refusing: DATABASE_MODE={s.database_mode!r} (need 'supabase').")
    if (s.database_env or "").lower() != "test":
        raise SystemExit(f"Refusing: database_env={s.database_env!r} (need 'test').")
    if not getattr(s, "enable_test_facilities", False):
        raise SystemExit("Refusing: ENABLE_TEST_FACILITIES is not true.")
    if not getattr(s, "allow_test_seed", False):
        raise SystemExit("Refusing: ALLOW_TEST_SEED is not true.")
    return s.database_url.replace("postgresql+asyncpg://", "postgresql://").replace("postgres+asyncpg://", "postgresql://")


async def _seed_facility(conn: asyncpg.Connection, f: dict) -> str:
    cap = f["max_concurrent_orders"]
    fid = await conn.fetchval(
        """
        insert into facilities
            (code, name, area, city, emirate, market, country, latitude, longitude,
             service_radius_km, capacity_daily, max_concurrent_orders, current_workload_pct,
             capacity_unit, operating_status, accepts_orders, is_active, quality_score, rating,
             review_count, supports_express, turnaround_hours, capacity_level, is_test_facility,
             is_test_data, environment, seed_source, created_by_seed)
        values ($1,$2,$3,'Dubai','Dubai','AE','AE',$4,$5,$6,$7,$7,$8,'orders_per_day',$9,true,true,
                $10,$11,$12,$13,$14,$15,true,true,'TEST','trial_facilities',true)
        on conflict (code) do update set
            name=excluded.name, area=excluded.area, latitude=excluded.latitude,
            longitude=excluded.longitude, service_radius_km=excluded.service_radius_km,
            capacity_daily=excluded.capacity_daily, max_concurrent_orders=excluded.max_concurrent_orders,
            current_workload_pct=excluded.current_workload_pct, operating_status=excluded.operating_status,
            quality_score=excluded.quality_score, rating=excluded.rating,
            review_count=excluded.review_count, supports_express=excluded.supports_express,
            turnaround_hours=excluded.turnaround_hours, capacity_level=excluded.capacity_level,
            is_test_facility=true, is_test_data=true, environment='TEST', updated_at=now()
        returning id
        """,
        f["code"], f["name"], f["area"], float(f["latitude"]), float(f["longitude"]),
        float(f["service_radius_km"]), cap, float(f["current_workload_pct"]),
        f["operating_status"], f["quality_score"], f["rating"], f["review_count"],
        f["supports_express"], f["turnaround_hours"], f["capacity_level"],
    )
    fid = str(fid)

    # Services (replace this facility's set).
    await conn.execute("delete from facility_services where facility_id = $1", fid)
    for code in sorted(f["services"]):
        await conn.execute(
            "insert into facility_services (facility_id, service_code, offered, express_ok) "
            "values ($1,$2,true,$3)",
            fid, code, code in f["express_services"])

    # Capabilities.
    await conn.execute("delete from facility_capabilities where facility_id = $1", fid)
    for cap_code in sorted(f["capabilities"]):
        await conn.execute(
            "insert into facility_capabilities (facility_id, capability_code, is_test_data, "
            "environment, seed_source, created_by_seed) values ($1,$2,true,'TEST','trial_facilities',true)",
            fid, cap_code)

    # Timings (0=Sun..6=Sat; missing day = closed).
    await conn.execute("delete from facility_timings where facility_id = $1", fid)
    for day in range(7):
        hours = f["hours"].get(day)
        if hours is None:
            await conn.execute(
                "insert into facility_timings (facility_id, day_of_week, is_closed) values ($1,$2,true)",
                fid, day)
        else:
            await conn.execute(
                "insert into facility_timings (facility_id, day_of_week, opens_at, closes_at, is_closed) "
                "values ($1,$2,$3,$4,false)",
                fid, day, _pt(hours[0]), _pt(hours[1]))
    return fid


async def _seed_driver(conn: asyncpg.Connection, fid: str, area: str, d: dict) -> None:
    trial_status = d["status"]
    # facility_drivers.status has no 'on_leave' value -> model leave via employment_status.
    if trial_status == "on_leave":
        status, employment = "free", "on_leave"
    else:
        status, employment = trial_status, "active"
    active = status != "offline"
    await conn.execute(
        """
        insert into facility_drivers
            (facility_id, name, driver_code, role, status, vehicle_type, area, active,
             is_test_driver, is_test_data, environment, employment_status, shift_start, shift_end,
             break_start, break_end, express_eligible, max_concurrent_assignments, seed_source, created_by_seed)
        values ($1,$2,$3,'driver',$4,'car',$5,$6,true,true,'TEST',$7,$8,$9,$10,$11,$12,1,'trial_facilities',true)
        on conflict (driver_code) where driver_code is not null do update set
            facility_id=excluded.facility_id, name=excluded.name, status=excluded.status,
            active=excluded.active, employment_status=excluded.employment_status,
            shift_start=excluded.shift_start, shift_end=excluded.shift_end,
            break_start=excluded.break_start, break_end=excluded.break_end,
            express_eligible=excluded.express_eligible, is_test_driver=true, updated_at=now()
        """,
        fid, d["name"], d["code"], status, area, active, employment,
        _pt(d.get("shift_start")), _pt(d.get("shift_end")), _pt(d.get("break_start")), _pt(d.get("break_end")),
        d["express_eligible"],
    )


async def main() -> None:
    conn = await asyncpg.connect(dsn=_dsn())
    try:
        for f in TRIAL_FACILITIES:
            async with conn.transaction():
                fid = await _seed_facility(conn, f)
                for d in f["drivers"]:
                    await _seed_driver(conn, fid, f["area"], d)
            print(f"  ok: {f['code']} ({len(f['drivers'])} driver(s))", flush=True)
        n_fac = await conn.fetchval("select count(*) from facilities where is_test_facility")
        n_drv = await conn.fetchval("select count(*) from facility_drivers where is_test_driver")
        print(f"\nSeeded. Test facilities={n_fac}, test drivers={n_drv}.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
