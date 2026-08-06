"""Apply the facility-order-experience migrations (000046-000048) to the dev/test
Supabase via asyncpg (psql is not installed locally).

Reads the connection string from the app settings' DATABASE_URL, normalises the
scheme for asyncpg, runs each migration file (all additive + idempotent), then
runs verification queries. Refuses to run unless DATABASE_MODE=supabase so it can
never touch the hermetic SQLite test DB.

Usage (from apps/whatsapp-agent):
    ./.venv/Scripts/python.exe scripts/apply_facility_experience_migrations.py
"""
from __future__ import annotations

import asyncio
import pathlib
import sys

import asyncpg

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from settings import get_settings  # noqa: E402

MIGRATIONS = [
    "20260806_000046_facility_order_experience.sql",
    "20260806_000047_facility_issue_structured_fields.sql",
    "20260806_000048_clarifications_quote_revisions.sql",
]

VERIFY = [
    ("order_notes.priority",
     "select 1 from information_schema.columns where table_name='order_notes' and column_name='priority'"),
    ("order_photos.order_item_id",
     "select 1 from information_schema.columns where table_name='order_photos' and column_name='order_item_id'"),
    ("order_photos.source",
     "select 1 from information_schema.columns where table_name='order_photos' and column_name='source'"),
    ("orders.facility_fee_snapshot",
     "select 1 from information_schema.columns where table_name='orders' and column_name='facility_fee_snapshot'"),
    ("facility_order_reviews table", "select to_regclass('public.facility_order_reviews')"),
    ("facility_issues.requires_price_revision",
     "select 1 from information_schema.columns where table_name='facility_issues' and column_name='requires_price_revision'"),
    ("facility_issues.photo_ids",
     "select 1 from information_schema.columns where table_name='facility_issues' and column_name='photo_ids'"),
    ("order_notes.facility_issue_id",
     "select 1 from information_schema.columns where table_name='order_notes' and column_name='facility_issue_id'"),
    ("facility_quote_revisions table", "select to_regclass('public.facility_quote_revisions')"),
]


def _dsn() -> str:
    settings = get_settings()
    if (settings.database_mode or "").lower() != "supabase":
        raise SystemExit(f"Refusing to run: DATABASE_MODE={settings.database_mode!r} (need 'supabase').")
    url = settings.database_url or ""
    # asyncpg wants a plain postgres DSN, not the SQLAlchemy +asyncpg dialect.
    return url.replace("postgresql+asyncpg://", "postgresql://").replace("postgres+asyncpg://", "postgresql://")


async def main() -> None:
    root = pathlib.Path(__file__).resolve().parents[3] / "supabase" / "migrations"
    conn = await asyncpg.connect(dsn=_dsn())
    try:
        for name in MIGRATIONS:
            sql = (root / name).read_text(encoding="utf-8")
            print(f"-> applying {name} ...", flush=True)
            await conn.execute(sql)
            print(f"  ok: {name}")
        print("\nVerification:")
        all_ok = True
        for label, q in VERIFY:
            val = await conn.fetchval(q)
            ok = val is not None
            all_ok = all_ok and ok
            print(f"  [{'ok' if ok else 'MISSING'}] {label}")
        print("\nAll migrations applied and verified." if all_ok else "\nSOME OBJECTS MISSING — review above.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
