"""Verify migration 000037 (facility_bank_details) is in effect on Supabase.

Checks the table, key columns, the RLS deny policy, and that plaintext IBAN /
account number columns do NOT exist (only *_ciphertext / *_last4), then runs an
insert round-trip inside a transaction that is ALWAYS rolled back.

Usage (from apps/whatsapp-agent, with DATABASE_MODE=supabase):
    python scripts/verify_facility_bank_details.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import database  # noqa: E402

_COLS = ("id", "facility_id", "account_holder_name", "bank_name", "swift_bic",
         "branch_name", "bank_country", "currency", "iban_ciphertext", "iban_last4",
         "account_number_ciphertext", "account_number_last4", "created_by_user_id",
         "updated_by_user_id", "created_at", "updated_at")


async def main() -> int:
    if not database.is_supabase_mode():
        print("Not supabase mode (DATABASE_MODE=supabase required). Aborting.")
        return 1
    pool = await database.get_pool()
    ok = True
    async with pool.acquire() as conn:
        has_table = await conn.fetchval("select to_regclass('public.facility_bank_details')")
        print(f"facility_bank_details table present : {bool(has_table)}")
        ok = ok and bool(has_table)

        cols = {
            r["column_name"]
            for r in await conn.fetch(
                "select column_name from information_schema.columns "
                "where table_name = 'facility_bank_details'"
            )
        }
        missing = [c for c in _COLS if c not in cols]
        print(f"columns present                     : {not missing}"
              + (f" (missing {missing})" if missing else ""))
        ok = ok and not missing

        # No plaintext IBAN / account_number columns may exist.
        leaked = [c for c in ("iban", "account_number") if c in cols]
        print(f"no plaintext secret columns         : {not leaked}"
              + (f" (LEAK {leaked})" if leaked else ""))
        ok = ok and not leaked

        pol = await conn.fetchval(
            "select 1 from pg_policies where policyname = 'facility_bank_details_no_public_access'")
        print(f"RLS deny policy                     : {bool(pol)}")
        ok = ok and bool(pol)

        fid = await conn.fetchval("select id from facilities order by created_at asc limit 1")
        if fid is None:
            print("insert round-trip                   : skipped (no facilities)")
        else:
            tr = conn.transaction()
            await tr.start()
            try:
                await conn.execute(
                    "insert into facility_bank_details "
                    "(facility_id, account_holder_name, bank_name, iban_ciphertext, "
                    " iban_last4, bank_country, currency, is_test_data) "
                    "values ($1,'Verify Co','Verify Bank','ciphertext-blob','1234','AE','AED',true) "
                    "on conflict (facility_id) do nothing",
                    fid,
                )
                n = await conn.fetchval(
                    "select count(*) from facility_bank_details where facility_id = $1", fid)
                print(f"insert round-trip                   : {'ok' if n >= 1 else 'FAILED'}")
                ok = ok and n >= 1
            finally:
                await tr.rollback()

    await database.close_pool()
    print("\nAll checks passed." if ok else "\nSome checks FAILED.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
