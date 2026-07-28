"""Verify migration 000029 is in effect on the connected Supabase project:
the order-state transition trigger + the RLS deny policies on
orders/messages/customers. Read-only except a transitions smoke-test that runs
inside a transaction which is ALWAYS rolled back (no data persisted).

Usage (from apps/whatsapp-agent, with DATABASE_MODE=supabase):
    python scripts/verify_order_state_and_rls.py
Exit code 0 = all good, non-zero = something missing/wrong.
"""
from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncpg  # noqa: E402

from db import database  # noqa: E402


async def _expect_block(conn, oid, new_status) -> bool:
    """True if the transition to new_status is correctly REJECTED by the trigger."""
    try:
        async with conn.transaction():  # savepoint
            await conn.execute("update orders set status = $2 where id = $1", oid, new_status)
        return False  # not blocked — bad
    except asyncpg.PostgresError:
        return True   # blocked — good


async def main() -> int:
    if not database.is_supabase_mode():
        print("Not supabase mode (DATABASE_MODE=supabase required). Aborting.")
        return 1
    pool = await database.get_pool()
    ok = True
    async with pool.acquire() as conn:
        trg = await conn.fetchval(
            "select 1 from pg_trigger where tgname='trg_orders_status_transition' and not tgisinternal")
        fn = await conn.fetchval(
            "select 1 from pg_proc where proname='enforce_order_status_transition'")
        pols = await conn.fetch(
            "select tablename from pg_policies where policyname in "
            "('orders_no_public_access','messages_no_public_access','customers_no_public_access')")
        pol_tables = sorted(p["tablename"] for p in pols)
        print(f"order-state trigger present : {bool(trg)}")
        print(f"trigger function present    : {bool(fn)}")
        print(f"RLS deny policies on        : {pol_tables}")
        ok = ok and bool(trg) and bool(fn) and set(pol_tables) == {"customers", "messages", "orders"}

        tr = conn.transaction()
        await tr.start()
        try:
            oid = await conn.fetchval(
                "insert into orders (order_id, status, is_test_data, created_by_seed) "
                "values ($1, 'draft', true, true) returning id", f"LK-VRFY-{uuid.uuid4().hex[:8]}")
            # legit transition must pass
            await conn.execute("update orders set status='pickup_scheduled' where id=$1", oid)
            legit = True
            # illegal transitions must be blocked
            blocked = all([
                await _expect_block(conn, oid, "draft"),       # resurrect
                await _expect_block(conn, oid, "banana"),       # vocabulary
            ])
            await conn.execute("update orders set status='completed' where id=$1", oid)
            terminal_locked = await _expect_block(conn, oid, "active")  # terminal immutability
        finally:
            await tr.rollback()
        print(f"legit draft->pickup_scheduled: {legit}")
        print(f"illegal transitions blocked  : {blocked}")
        print(f"terminal immutability        : {terminal_locked}")
        ok = ok and legit and blocked and terminal_locked

    print("\nRESULT:", "ALL GOOD" if ok else "FAILED — see above")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
