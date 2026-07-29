"""Apply migration 000030 (Facilities Management) to the dev/test Supabase project.

Runs ``supabase/migrations/20260729_000030_facilities_management.sql`` — additive
+ idempotent, so it is safe to run more than once. It adds the facilities-management
columns (full_address, quality_score, capacity_unit, onboarding_source,
created_by/updated_by), the facility_timings.is_24h flag, and the facility_audit_log
table + RLS deny policy.

There is no generic migration runner in this repo (each migration is applied
out-of-band); this mirrors the DDL-apply half of scripts/seed_service_catalogue.py.

Usage (from apps/whatsapp-agent, with DATABASE_MODE=supabase and DATABASE_ENV=test):
    python scripts/apply_facilities_management.py

Guards: refuses to run against a production environment and requires the
dev/test Supabase project (same _base_problems guard as the seed scripts).
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
    / "supabase" / "migrations" / "20260729_000030_facilities_management.sql"
)


async def _main() -> int:
    settings = get_settings()
    problems = _base_problems(settings)
    if problems:
        print("Refusing to apply migration 000030:")
        for p in problems:
            print(f"  - {p}")
        return 2
    if not _MIGRATION.exists():
        print(f"Migration file not found: {_MIGRATION}")
        return 2

    print(
        f"Applying {_MIGRATION.name} to {settings.database_mode} "
        f"({settings.database_env})"
    )
    sql = _MIGRATION.read_text(encoding="utf-8")
    pool = await database.get_pool()
    try:
        async with pool.acquire() as conn:
            # asyncpg runs the whole multi-statement DDL script (no params).
            async with conn.transaction():
                await conn.execute(sql)
    finally:
        await database.close_pool()
    print("Done. Run scripts/verify_facilities_management.py to confirm.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
