"""Verify migration 000038 (facility & driver ratings) is in effect on Supabase.

Checks all four tables, the score/overall CHECK constraints, and the RLS deny
policies, then runs a facility-evaluation insert round-trip (header + factor)
inside a transaction that is ALWAYS rolled back.

Usage (from apps/whatsapp-agent, with DATABASE_MODE=supabase):
    python scripts/verify_facility_driver_ratings.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import database  # noqa: E402

_TABLES = ("facility_evaluations", "facility_evaluation_factors",
           "driver_evaluations", "driver_evaluation_factors")
_CONSTRAINTS = ("facility_evaluations_overall_chk", "facility_eval_factor_score_chk",
                "driver_evaluations_overall_chk", "driver_eval_factor_score_chk")


async def main() -> int:
    if not database.is_supabase_mode():
        print("Not supabase mode (DATABASE_MODE=supabase required). Aborting.")
        return 1
    pool = await database.get_pool()
    ok = True
    async with pool.acquire() as conn:
        for t in _TABLES:
            present = await conn.fetchval(f"select to_regclass('public.{t}')")
            print(f"{t:32}: {bool(present)}")
            ok = ok and bool(present)

        for c in _CONSTRAINTS:
            present = await conn.fetchval("select 1 from pg_constraint where conname = $1", c)
            print(f"{c:32}: {bool(present)}")
            ok = ok and bool(present)

        for t in _TABLES:
            pol = await conn.fetchval(
                "select 1 from pg_policies where policyname = $1", f"{t}_no_public_access")
            print(f"{t}_no_public_access RLS       : {bool(pol)}")
            ok = ok and bool(pol)

        fid = await conn.fetchval("select id from facilities order by created_at asc limit 1")
        if fid is None:
            print("insert round-trip               : skipped (no facilities)")
        else:
            tr = conn.transaction()
            await tr.start()
            try:
                eid = await conn.fetchval(
                    "insert into facility_evaluations "
                    "(facility_id, overall_score, status, is_test_data) "
                    "values ($1, 4.2, 'published', true) returning id", fid)
                await conn.execute(
                    "insert into facility_evaluation_factors "
                    "(evaluation_id, factor_key, factor_label, score, weight, weighted_score) "
                    "values ($1,'service_quality','Service quality',4.0,1.0,4.0)", eid)
                n = await conn.fetchval(
                    "select count(*) from facility_evaluation_factors where evaluation_id = $1", eid)
                print(f"insert round-trip               : {'ok' if n == 1 else 'FAILED'}")
                ok = ok and n == 1
                # score CHECK rejects an out-of-range factor score.
                try:
                    await conn.execute(
                        "insert into facility_evaluation_factors "
                        "(evaluation_id, factor_key, factor_label, score) "
                        "values ($1,'bad','Bad',9.0)", eid)
                    print("score CHECK rejects >5          : FAILED (accepted 9)")
                    ok = False
                except Exception:
                    print("score CHECK rejects >5          : ok")
            finally:
                await tr.rollback()

    await database.close_pool()
    print("\nAll checks passed." if ok else "\nSome checks FAILED.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
