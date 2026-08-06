"""Apply a single migration file to the dev/test Supabase via asyncpg.

Usage (from apps/whatsapp-agent):
    ./.venv/Scripts/python.exe scripts/apply_migration.py <migration_filename.sql>
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
    return s.database_url.replace("postgresql+asyncpg://", "postgresql://").replace("postgres+asyncpg://", "postgresql://")


async def main() -> None:
    name = sys.argv[1]
    path = pathlib.Path(__file__).resolve().parents[3] / "supabase" / "migrations" / name
    sql = path.read_text(encoding="utf-8")
    conn = await asyncpg.connect(dsn=_dsn())
    try:
        print(f"-> applying {name} ...", flush=True)
        await conn.execute(sql)
        print(f"  ok: {name}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
