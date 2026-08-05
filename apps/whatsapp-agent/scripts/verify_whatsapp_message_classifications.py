"""Verify migration 000039 (WhatsApp intent classifications) is in effect on Supabase.

Checks the table, the idempotency unique constraint, the range CHECK, the RLS deny
policy, and runs an insert round-trip (including a duplicate that must be a no-op
via ON CONFLICT) inside a transaction that is ALWAYS rolled back.

Usage (from apps/whatsapp-agent, with DATABASE_MODE=supabase):
    python scripts/verify_whatsapp_message_classifications.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import database  # noqa: E402

_TABLE = "whatsapp_message_classifications"
_CONSTRAINTS = ("wmc_provider_msg_version_uniq", "wmc_confidence_chk")


async def main() -> int:
    if not database.is_supabase_mode():
        print("Not supabase mode (DATABASE_MODE=supabase required). Aborting.")
        return 1
    pool = await database.get_pool()
    ok = True
    async with pool.acquire() as conn:
        present = await conn.fetchval(f"select to_regclass('public.{_TABLE}')")
        print(f"{_TABLE:34}: {bool(present)}")
        ok = ok and bool(present)

        for c in _CONSTRAINTS:
            has = await conn.fetchval("select 1 from pg_constraint where conname = $1", c)
            print(f"{c:34}: {bool(has)}")
            ok = ok and bool(has)

        pol = await conn.fetchval(
            "select 1 from pg_policies where policyname = $1", f"{_TABLE}_no_public_access")
        print(f"{_TABLE}_no_public_access RLS : {bool(pol)}")
        ok = ok and bool(pol)

        # insert + duplicate (ON CONFLICT) round-trip, always rolled back.
        tr = conn.transaction()
        await tr.start()
        try:
            await conn.execute(
                f"insert into {_TABLE} (provider, provider_message_id, classification_version, "
                "primary_intent, is_test_data) values "
                "('evolution','verify_msg_1','2026_08_05','GREETING',true)")
            # duplicate on (provider, provider_message_id, version) → no-op
            await conn.execute(
                f"insert into {_TABLE} (provider, provider_message_id, classification_version, "
                "primary_intent, is_test_data) values "
                "('evolution','verify_msg_1','2026_08_05','SERVICE_SELECTION',true) "
                "on conflict (provider, provider_message_id, classification_version) do nothing")
            n = await conn.fetchval(
                f"select count(*) from {_TABLE} where provider_message_id = 'verify_msg_1'")
            print(f"idempotent insert (1 row)         : {'ok' if n == 1 else f'FAILED ({n})'}")
            ok = ok and n == 1
            # confidence CHECK rejects out-of-range
            try:
                await conn.execute(
                    f"insert into {_TABLE} (provider, provider_message_id, classification_version, "
                    "primary_intent, intent_confidence, is_test_data) values "
                    "('evolution','verify_bad','2026_08_05','GREETING',5.0,true)")
                print("confidence CHECK rejects >1       : FAILED (accepted 5.0)")
                ok = False
            except Exception:
                print("confidence CHECK rejects >1       : ok")
        finally:
            await tr.rollback()
    await database.close_pool()
    print("RESULT:", "ok" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
