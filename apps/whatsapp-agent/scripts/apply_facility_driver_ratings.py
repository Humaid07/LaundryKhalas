"""Apply migration 000038 (facility & driver ratings) to the dev/test Supabase project.

Runs ``supabase/migrations/20260801_000038_facility_driver_ratings.sql`` — additive
+ idempotent. Adds facility_evaluations / facility_evaluation_factors /
driver_evaluations / driver_evaluation_factors with constraints, indexes, triggers
and RLS deny policies.

Usage (from apps/whatsapp-agent, with DATABASE_MODE=supabase and DATABASE_ENV=test):
    python scripts/apply_facility_driver_ratings.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import database  # noqa: E402
from scripts._safety import _base_problems  # noqa: E402
from settings import get_settings  # noqa: E402

_MIGRATION = (
    Path(__file__).resolve().parents[3]
    / "supabase" / "migrations" / "20260801_000038_facility_driver_ratings.sql"
)


async def _main() -> int:
    settings = get_settings()
    problems = _base_problems(settings)
    if problems:
        print("Refusing to apply migration 000038:")
        for p in problems:
            print(f"  - {p}")
        return 2
    if not _MIGRATION.exists():
        print(f"Migration file not found: {_MIGRATION}")
        return 2
    print(f"Applying {_MIGRATION.name} to {settings.database_mode} ({settings.database_env})")
    sql = _MIGRATION.read_text(encoding="utf-8")
    pool = await database.get_pool()
    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(sql)
    finally:
        await database.close_pool()
    print("Done. Run scripts/verify_facility_driver_ratings.py to confirm.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
