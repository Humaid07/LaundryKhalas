"""Verify migration 000030 (Facilities Management) is in effect on Supabase.

Checks the new facilities columns, facility_timings.is_24h, and the
facility_audit_log table + RLS deny policy exist, then runs an
insert/update/audit round-trip inside a transaction that is ALWAYS rolled back
(no data persisted).

Usage (from apps/whatsapp-agent, with DATABASE_MODE=supabase):
    python scripts/verify_facilities_management.py
Exit code 0 = all good, non-zero = something missing/wrong.
"""
from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import database  # noqa: E402

_FACILITY_COLS = ("full_address", "quality_score", "capacity_unit",
                  "onboarding_source", "created_by", "updated_by")


async def main() -> int:
    if not database.is_supabase_mode():
        print("Not supabase mode (DATABASE_MODE=supabase required). Aborting.")
        return 1
    pool = await database.get_pool()
    ok = True
    async with pool.acquire() as conn:
        cols = {
            r["column_name"]
            for r in await conn.fetch(
                "select column_name from information_schema.columns where table_name = 'facilities'"
            )
        }
        missing = [c for c in _FACILITY_COLS if c not in cols]
        print(f"facilities new columns present : {not missing}"
              + (f" (missing {missing})" if missing else ""))
        ok = ok and not missing

        has_24h = await conn.fetchval(
            "select 1 from information_schema.columns "
            "where table_name = 'facility_timings' and column_name = 'is_24h'"
        )
        print(f"facility_timings.is_24h present : {bool(has_24h)}")
        ok = ok and bool(has_24h)

        has_audit = await conn.fetchval("select to_regclass('public.facility_audit_log')")
        print(f"facility_audit_log table present: {bool(has_audit)}")
        ok = ok and bool(has_audit)

        pol = await conn.fetchval(
            "select 1 from pg_policies where policyname = 'facility_audit_log_no_public_access'"
        )
        print(f"facility_audit_log RLS deny     : {bool(pol)}")
        ok = ok and bool(pol)

        # Round-trip smoke test (rolled back).
        tr = conn.transaction()
        await tr.start()
        try:
            code = f"VRFY-{uuid.uuid4().hex[:8]}"
            fid = await conn.fetchval(
                "insert into facilities (code, name, emirate, capacity_daily, capacity_unit, "
                "onboarding_source, quality_score, full_address) "
                "values ($1, 'Verify Facility', 'Dubai', 40, 'kg_per_day', 'admin_dashboard', 88.5, "
                "'Some St, Dubai') returning id",
                code,
            )
            await conn.execute(
                "update facilities set operating_status = 'busy', updated_at = now() where id = $1", fid
            )
            await conn.execute(
                "insert into facility_audit_log (facility_id, action, actor_type, source_app, "
                "before_json, after_json) values ($1, 'status_changed', 'internal', 'admin_dashboard', "
                "'{\"operating_status\": \"open\"}', '{\"operating_status\": \"busy\"}')",
                fid,
            )
            n = await conn.fetchval(
                "select count(*) from facility_audit_log where facility_id = $1", fid
            )
            print(f"insert/update/audit round-trip  : {'ok' if n == 1 else 'FAILED'}")
            ok = ok and n == 1
        finally:
            await tr.rollback()  # never persist the smoke-test rows

    await database.close_pool()
    print("\nAll checks passed." if ok else "\nSome checks FAILED.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
