"""Verify connectivity to the dev/test Supabase project (read-only).

Usage (from apps/whatsapp-agent, with .env configured):
    python scripts/verify_supabase_connection.py

Reports DB mode, connectivity, whether the expected tables exist, and how many
seeded test rows are present. Never writes. Never prints secrets. Exits non-zero
on failure so it is CI-friendly.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from _safety import SEED_BATCH_ID, SEED_TABLES_DELETE_ORDER  # noqa: E402
from db import database  # noqa: E402
from settings import get_settings  # noqa: E402

EXPECTED_TABLES = sorted(SEED_TABLES_DELETE_ORDER)


async def main() -> int:
    s = get_settings()
    print("LaundryKhalas — Supabase dev/test connection check")
    print(f"  APP_ENV               = {s.app_env}")
    print(f"  DATABASE_ENV          = {s.database_env}")
    print(f"  DATABASE_MODE         = {s.database_mode}")
    print(f"  SUPABASE_PROJECT_TYPE = {s.supabase_project_type}")

    if s.database_mode.lower() != "supabase":
        print("\n[SKIP] DATABASE_MODE is not 'supabase'; nothing to verify against Postgres.")
        return 0

    health = await database.db_health()
    print(f"\n  health: {health}")
    if not health.get("connected"):
        print("\n[FAIL] Could not connect to Supabase. Check DATABASE_URL / network.")
        return 1

    # Which expected tables exist?
    rows = await database.fetch(
        "select table_name from information_schema.tables where table_schema = 'public'"
    )
    present = {r["table_name"] for r in rows}
    missing = [t for t in EXPECTED_TABLES if t not in present]
    print("\n  tables present:", sorted(t for t in EXPECTED_TABLES if t in present))
    if missing:
        print("  tables MISSING :", missing)
        print("\n[WARN] Apply the schema first: run migration 000001 (supabase db push).")

    # Seeded row counts (safe read).
    print("\n  seeded test rows (seed_batch_id =", SEED_BATCH_ID + "):")
    for table in EXPECTED_TABLES:
        if table not in present:
            continue
        count = await database.fetchval(
            f"select count(*) from {table} where seed_batch_id = $1", SEED_BATCH_ID
        )
        print(f"    {table:<16} {count}")

    await database.close_pool()
    print("\n[OK] Supabase dev/test connection verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
