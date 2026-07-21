"""Seed FAKE/DEMO WhatsApp-agent data into the dev/test Supabase project.

Refuses to run unless the environment is unambiguously dev/test:
    ALLOW_TEST_SEED=true, DATABASE_ENV=test, APP_ENV != production,
    SUPABASE_PROJECT_TYPE=test, DATABASE_MODE=supabase.

It executes the SAME seed SQL as the migration
(supabase/migrations/20260721_000002_seed_whatsapp_agent_test_data.sql), which
uses fixed UUIDs + `on conflict do nothing`, so running it is idempotent and
never duplicates rows. The schema (migration 000001) must already be applied.

Usage (from apps/whatsapp-agent):
    python scripts/seed_supabase_test_data.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from _safety import SEED_BATCH_ID, SEED_TABLES_DELETE_ORDER, check_seed_allowed  # noqa: E402
from db import database  # noqa: E402
from settings import get_settings  # noqa: E402

_SEED_SQL = (
    Path(__file__).resolve().parents[2]
    / "supabase"
    / "migrations"
    / "20260721_000002_seed_whatsapp_agent_test_data.sql"
)


async def main() -> int:
    s = get_settings()
    problems = check_seed_allowed(s)
    if problems:
        print("Refusing to seed — environment is not a confirmed dev/test Supabase project:")
        for p in problems:
            print(f"  - {p}")
        return 1

    if not _SEED_SQL.exists():
        print(f"Seed SQL not found: {_SEED_SQL}")
        return 1

    sql = _SEED_SQL.read_text(encoding="utf-8")
    print(f"Seeding dev/test Supabase (batch {SEED_BATCH_ID}) …")
    try:
        pool = await database.get_pool()
    except Exception as exc:  # noqa: BLE001
        print(f"Could not connect to Supabase: {exc}")
        return 1

    async with pool.acquire() as conn:
        # Fail clearly if the schema hasn't been applied yet.
        has_conversations = await conn.fetchval(
            "select to_regclass('public.conversations') is not null"
        )
        if not has_conversations:
            print("Schema not found. Apply migration 000001 first (supabase db push).")
            return 1
        async with conn.transaction():
            await conn.execute(sql)

    # Report what is now present for this batch.
    print("Seeded rows by table:")
    for table in reversed(SEED_TABLES_DELETE_ORDER):  # parent-first reads nicer
        count = await database.fetchval(
            f"select count(*) from {table} where seed_batch_id = $1", SEED_BATCH_ID
        )
        print(f"  {table:<16} {count}")

    await database.close_pool()
    print("\nDone. All seeded rows are marked is_test_data=true, is_demo=true, environment='dev'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
