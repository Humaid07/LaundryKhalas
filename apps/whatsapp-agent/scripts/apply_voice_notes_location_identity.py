"""Apply migration 000033 (voice/notes/location/identity) to dev/test Supabase.

Runs ``supabase/migrations/20260730_000033_voice_notes_location_identity.sql`` —
additive + idempotent, safe to run more than once. Adds conversation voice-
escalation columns, order structured-address/location/notes-snapshot/handoff
columns, customer identity columns, and the ``order_notes`` table.

There is no generic migration runner in this repo; each migration has a
hand-written apply/verify pair (mirrors scripts/apply_order_photos.py).

Usage (from apps/whatsapp-agent, with DATABASE_MODE=supabase and DATABASE_ENV=test):
    python scripts/apply_voice_notes_location_identity.py
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
    / "supabase" / "migrations" / "20260730_000033_voice_notes_location_identity.sql"
)


async def _main() -> int:
    settings = get_settings()
    problems = _base_problems(settings)
    if problems:
        print("Refusing to apply migration 000033:")
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
    print("Done. Run scripts/verify_voice_notes_location_identity.py to confirm.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
