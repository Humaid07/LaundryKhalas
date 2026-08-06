"""Remove ONLY the trial (TEST) facilities/drivers + their dependent test rows.

NEVER touches production data — every delete is guarded by is_test_facility /
is_test_driver / is_test_data. Requires an explicit TEST-environment confirmation.

GUARDS (all required): DATABASE_MODE=supabase, database_env=test, ALLOW_TEST_RESET=true.

Usage (from apps/whatsapp-agent):
    ALLOW_TEST_RESET=true ./.venv/Scripts/python.exe scripts/reset_test_facilities_and_drivers.py --confirm TEST
"""
from __future__ import annotations

import asyncio
import pathlib
import sys

import asyncpg

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from settings import get_settings  # noqa: E402


def _dsn() -> str:
    s = get_settings()
    if (s.database_mode or "").lower() != "supabase":
        raise SystemExit(f"Refusing: DATABASE_MODE={s.database_mode!r} (need 'supabase').")
    if (s.database_env or "").lower() != "test":
        raise SystemExit(f"Refusing: database_env={s.database_env!r} (need 'test').")
    if not getattr(s, "allow_test_reset", False):
        raise SystemExit("Refusing: ALLOW_TEST_RESET is not true.")
    if "--confirm" not in sys.argv or "TEST" not in sys.argv:
        raise SystemExit("Refusing: pass --confirm TEST to confirm the TEST-environment reset.")
    return s.database_url.replace("postgresql+asyncpg://", "postgresql://").replace("postgres+asyncpg://", "postgresql://")


async def main() -> None:
    conn = await asyncpg.connect(dsn=_dsn())
    try:
        async with conn.transaction():
            # Children first (defensive — FKs also cascade on facility delete).
            await conn.execute(
                "delete from driver_assignments where driver_id in "
                "(select id from facility_drivers where is_test_driver)")
            await conn.execute("delete from facility_drivers where is_test_driver")
            await conn.execute(
                "delete from facility_capabilities where facility_id in "
                "(select id from facilities where is_test_facility)")
            await conn.execute(
                "delete from facility_services where facility_id in "
                "(select id from facilities where is_test_facility)")
            await conn.execute(
                "delete from facility_timings where facility_id in "
                "(select id from facilities where is_test_facility)")
            await conn.execute("delete from routing_decisions where is_test_data")
            deleted = await conn.fetchval(
                "with d as (delete from facilities where is_test_facility returning 1) "
                "select count(*) from d")
        print(f"Reset complete. Removed {deleted} test facilities (+ their test drivers/services/"
              f"capabilities/timings/routing decisions). Production data untouched.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
