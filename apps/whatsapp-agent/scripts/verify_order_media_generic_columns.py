"""Verify migration 000034 (order_media generic columns) on dev/test Supabase.

Read-only. Confirms the generic media columns exist on ``order_photos`` and the
stage CHECK was expanded to the eight stages. Mirrors scripts/verify_order_photos.py.

Usage (from apps/whatsapp-agent, DATABASE_MODE=supabase, DATABASE_ENV=test):
    python scripts/verify_order_media_generic_columns.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import database  # noqa: E402
from settings import get_settings  # noqa: E402

_EXPECTED_COLS = [
    "bucket", "checksum_sha256", "width", "height", "duration_seconds",
    "source_channel", "visibility_scope", "status",
]
_EXPECTED_STAGES = {
    "intake", "pre_dispatch", "customer_reference", "damage_report",
    "issue_photo", "quality_check", "pickup_proof", "delivery_proof",
}


async def _main() -> int:
    settings = get_settings()
    if settings.database_mode.lower() != "supabase":
        print(f"DATABASE_MODE must be 'supabase' (got '{settings.database_mode}').")
        return 2

    pool = await database.get_pool()
    ok = True
    try:
        async with pool.acquire() as conn:
            cols = {
                r["column_name"]
                for r in await conn.fetch(
                    "select column_name from information_schema.columns "
                    "where table_schema = 'public' and table_name = 'order_photos'"
                )
            }
            missing = [c for c in _EXPECTED_COLS if c not in cols]
            if missing:
                ok = False
                print(f"MISSING columns: {missing}")
            else:
                print(f"OK: all {len(_EXPECTED_COLS)} generic media columns present.")

            check = await conn.fetchval(
                "select pg_get_constraintdef(oid) from pg_constraint "
                "where conname = 'order_photos_stage_chk'"
            )
            print(f"stage CHECK: {check}")
            if check and all(s in check for s in _EXPECTED_STAGES):
                print("OK: stage CHECK covers all 8 stages.")
            else:
                ok = False
                print("stage CHECK does NOT cover the expected 8 stages.")

            for name in ("order_photos_visibility_chk", "order_photos_status_chk"):
                exists = await conn.fetchval(
                    "select 1 from pg_constraint where conname = $1", name
                )
                print(f"{name}: {'present' if exists else 'MISSING'}")
                ok = ok and bool(exists)
    finally:
        await database.close_pool()

    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
