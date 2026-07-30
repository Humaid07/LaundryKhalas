"""Apply migration 000034 (order_media generic columns) to dev/test Supabase.

Runs ``supabase/migrations/20260730_000034_order_media_generic_columns.sql`` —
additive + idempotent, safe to run more than once. Extends ``order_photos`` into
the unified, R2-backed order-media record (bucket, checksum_sha256, width, height,
duration_seconds, source_channel, visibility_scope, status) and expands the stage
CHECK. Mirrors scripts/apply_order_photos.py (no generic migration runner exists;
each migration has a hand-written apply/verify pair).

Usage (from apps/whatsapp-agent, with DATABASE_MODE=supabase and DATABASE_ENV=test):
    python scripts/apply_order_media_generic_columns.py

Guards: refuses to run unless the environment is unambiguously the dev/test
Supabase project (same _base_problems guard as the seed scripts). Never production.
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
    / "supabase" / "migrations" / "20260730_000034_order_media_generic_columns.sql"
)


async def _main() -> int:
    settings = get_settings()
    problems = _base_problems(settings)
    if problems:
        print("Refusing to apply migration 000034:")
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
    print("Done. Run scripts/verify_order_media_generic_columns.py to confirm.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
