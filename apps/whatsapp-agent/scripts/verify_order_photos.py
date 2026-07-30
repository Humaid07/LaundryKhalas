"""Verify migration 000032 (order_photos) is in effect on Supabase.

Checks the order_photos table, its key columns, the stage/provider CHECK
constraints, and the RLS deny policy exist, then runs an insert round-trip
inside a transaction that is ALWAYS rolled back (no data persisted).

Usage (from apps/whatsapp-agent, with DATABASE_MODE=supabase):
    python scripts/verify_order_photos.py
Exit code 0 = all good, non-zero = something missing/wrong.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import database  # noqa: E402

_COLS = ("id", "order_id", "facility_id", "stage", "storage_provider", "storage_key",
         "public_url", "file_name", "content_type", "file_size", "uploaded_by_user_id",
         "uploaded_by_name", "metadata", "created_at", "deleted_at")


async def main() -> int:
    if not database.is_supabase_mode():
        print("Not supabase mode (DATABASE_MODE=supabase required). Aborting.")
        return 1
    pool = await database.get_pool()
    ok = True
    async with pool.acquire() as conn:
        has_table = await conn.fetchval("select to_regclass('public.order_photos')")
        print(f"order_photos table present      : {bool(has_table)}")
        ok = ok and bool(has_table)

        cols = {
            r["column_name"]
            for r in await conn.fetch(
                "select column_name from information_schema.columns where table_name = 'order_photos'"
            )
        }
        missing = [c for c in _COLS if c not in cols]
        print(f"order_photos columns present    : {not missing}"
              + (f" (missing {missing})" if missing else ""))
        ok = ok and not missing

        for conname in ("order_photos_stage_chk", "order_photos_provider_chk"):
            present = await conn.fetchval(
                "select 1 from pg_constraint where conname = $1", conname)
            print(f"{conname:32}: {bool(present)}")
            ok = ok and bool(present)

        pol = await conn.fetchval(
            "select 1 from pg_policies where policyname = 'order_photos_no_public_access'")
        print(f"order_photos RLS deny policy    : {bool(pol)}")
        ok = ok and bool(pol)

        # Round-trip smoke test (rolled back) — needs a real order to FK against.
        order_uuid = await conn.fetchval("select id from orders order by created_at desc limit 1")
        if order_uuid is None:
            print("insert round-trip               : skipped (no orders to reference)")
        else:
            tr = conn.transaction()
            await tr.start()
            try:
                fid = await conn.fetchval("select facility_id from orders where id = $1", order_uuid)
                pid = await conn.fetchval(
                    "insert into order_photos "
                    "(order_id, facility_id, stage, storage_provider, storage_key, file_name, "
                    " content_type, file_size, uploaded_by_name, is_test_data) "
                    "values ($1,$2,'intake','local','k/order-photo-x.jpg','order-photo-x.jpg',"
                    " 'image/jpeg', 123, 'Verify', true) returning id",
                    order_uuid, fid,
                )
                n = await conn.fetchval(
                    "select count(*) from order_photos where id = $1 and deleted_at is null", pid)
                print(f"insert round-trip               : {'ok' if n == 1 else 'FAILED'}")
                ok = ok and n == 1
                # stage CHECK rejects an unknown stage.
                try:
                    await conn.execute(
                        "insert into order_photos (order_id, facility_id, stage, storage_key, "
                        "file_name, content_type) values ($1,$2,'bogus','k','f','image/jpeg')",
                        order_uuid, fid)
                    print("stage CHECK rejects bad value   : FAILED (accepted 'bogus')")
                    ok = False
                except Exception:
                    print("stage CHECK rejects bad value   : ok")
            finally:
                await tr.rollback()

    await database.close_pool()
    print("\nAll checks passed." if ok else "\nSome checks FAILED.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
