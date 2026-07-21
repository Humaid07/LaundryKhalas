"""Delete ONLY seeded test data from the dev/test Supabase project.

Refuses to run unless the environment is unambiguously dev/test:
    ALLOW_TEST_RESET=true, DATABASE_ENV=test, APP_ENV != production,
    SUPABASE_PROJECT_TYPE=test, DATABASE_MODE=supabase.

Safety rules (enforced in SQL):
  * Only deletes rows where is_test_data = true AND created_by_seed = true.
  * Scoped to the seed batch id by default.
  * NEVER truncates. NEVER deletes rows where is_test_data = false.

Usage (from apps/whatsapp-agent):
    python scripts/reset_supabase_test_data.py            # delete the seed batch
    python scripts/reset_supabase_test_data.py --all-test # delete ALL seeded test rows
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from _safety import SEED_BATCH_ID, SEED_TABLES_DELETE_ORDER, check_reset_allowed  # noqa: E402
from db import database  # noqa: E402
from settings import get_settings  # noqa: E402


async def main(argv: list[str]) -> int:
    s = get_settings()
    problems = check_reset_allowed(s)
    if problems:
        print("Refusing to reset — environment is not a confirmed dev/test Supabase project:")
        for p in problems:
            print(f"  - {p}")
        return 1

    scope_all = "--all-test" in argv
    try:
        pool = await database.get_pool()
    except Exception as exc:  # noqa: BLE001
        print(f"Could not connect to Supabase: {exc}")
        return 1

    # Guard clause is baked into every DELETE: is_test_data AND created_by_seed.
    # Non-test/production-style rows can never match, by construction.
    where = "is_test_data = true and created_by_seed = true"
    args: list = []
    if not scope_all:
        where += " and seed_batch_id = $1"
        args = [SEED_BATCH_ID]

    total = 0
    print("Deleting seeded test data" + ("" if scope_all else f" (batch {SEED_BATCH_ID})") + " …")
    async with pool.acquire() as conn:
        async with conn.transaction():
            for table in SEED_TABLES_DELETE_ORDER:  # child-before-parent
                if not await conn.fetchval(f"select to_regclass('public.{table}') is not null"):
                    continue
                status = await conn.execute(f"delete from {table} where {where}", *args)
                # asyncpg returns e.g. "DELETE 6"
                n = int(status.split()[-1]) if status.startswith("DELETE") else 0
                total += n
                print(f"  {table:<16} -{n}")

    await database.close_pool()
    print(f"\nDone. Deleted {total} seeded test rows. Non-test rows were never touched.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(sys.argv[1:])))
