"""Reset ALL live-test state for the single approved test number (dev/test Supabase ONLY).

Hard-restricted to ONE phone number (``ALLOWED_PHONE`` below) — it refuses to run
for any other number, so it can never be pointed at an arbitrary customer.

Deletes the customer row plus their conversations and orders for that phone. FK
behaviour guarantees a clean wipe with no orphan-violation:
  * messages / conversation_turns / agent_flags / human_takeovers /
    approval_queue           -> ON DELETE CASCADE from conversations
  * order_events / order_notes / order_photos -> ON DELETE CASCADE from orders
  * everything else (tickets, complaints, pending_tasks, campaign_sends,
    b2b_leads, facility_*)   -> ON DELETE SET NULL

Refuses to run outside a confirmed dev/test Supabase project.

Usage (from apps/whatsapp-agent, with the venv):
    python scripts/reset_customer_by_phone.py +971543216640
    python scripts/reset_customer_by_phone.py +971543216640 --yes   # skip prompt
    python scripts/reset_customer_by_phone.py --yes                 # phone defaults to ALLOWED_PHONE
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import database  # noqa: E402
from services.privacy import hash_phone, mask_phone  # noqa: E402
from settings import get_settings  # noqa: E402

# The ONLY phone this script may reset. Any other number is refused outright.
ALLOWED_PHONE = "+971543216640"


def _guard(s) -> list[str]:
    problems: list[str] = []
    if getattr(s, "database_mode", None) != "supabase":
        problems.append("DATABASE_MODE must be 'supabase'")
    if getattr(s, "database_env", None) != "test":
        problems.append("DATABASE_ENV must be 'test'")
    if str(getattr(s, "app_env", "")).lower() == "production":
        problems.append("APP_ENV must not be 'production'")
    if getattr(s, "supabase_project_type", None) not in (None, "test"):
        problems.append("SUPABASE_PROJECT_TYPE must be 'test'")
    return problems


async def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    # Phone defaults to the single approved number; if supplied it must match it.
    phone = (args[0].strip() if args else ALLOWED_PHONE)
    if not phone.startswith("+"):
        phone = "+" + phone
    if phone != ALLOWED_PHONE:
        print(f"Refusing to run — this script may only reset {ALLOWED_PHONE}, "
              f"not {mask_phone(phone)}.")
        return 1
    assume_yes = "--yes" in argv

    s = get_settings()
    problems = _guard(s)
    if problems:
        print("Refusing to run — not a confirmed dev/test Supabase project:")
        for p in problems:
            print(f"  - {p}")
        return 1

    phash = hash_phone(phone)
    pool = await database.get_pool()
    async with pool.acquire() as conn:
        cust = await conn.fetchrow(
            "select id, display_name, created_at from customers where phone_hash = $1 "
            "order by created_at asc limit 1",
            phash,
        )
        if cust is None:
            print(f"No customer found for {mask_phone(phone)} (hash {phash[:8]}…). Nothing to do.")
            return 0
        cid = cust["id"]
        convos = await conn.fetch("select id from conversations where customer_id = $1", cid)
        convo_ids = [r["id"] for r in convos]
        n_orders = await conn.fetchval(
            "select count(*) from orders where customer_id = $1 "
            "or (conversation_id = any($2::uuid[]))",
            cid, convo_ids,
        )
        n_msgs = 0
        if convo_ids:
            n_msgs = await conn.fetchval(
                "select count(*) from messages where conversation_id = any($1::uuid[])", convo_ids
            )

        print(f"Target customer   : {mask_phone(phone)}  name={cust['display_name']!r}")
        print(f"  conversations   : {len(convo_ids)}")
        print(f"  messages        : {n_msgs}")
        print(f"  orders          : {n_orders}")

        if not assume_yes:
            print("\nRe-run with --yes to perform the delete.")
            return 0

        async with conn.transaction():
            # orders first (order_events/notes/photos cascade); flags/tickets SET NULL
            o1 = await conn.execute("delete from orders where customer_id = $1", cid)
            o2 = "DELETE 0"
            if convo_ids:
                o2 = await conn.execute(
                    "delete from orders where conversation_id = any($1::uuid[])", convo_ids
                )
            # conversations (messages/turns/flags/takeovers/approval_queue cascade)
            c1 = await conn.execute("delete from conversations where customer_id = $1", cid)
            # finally the customer
            c2 = await conn.execute("delete from customers where id = $1", cid)

        print("\nDeleted:")
        print(f"  orders (by customer)      {o1}")
        print(f"  orders (by conversation)  {o2}")
        print(f"  conversations             {c1}")
        print(f"  customer                  {c2}")
        print(f"\nDone. {mask_phone(phone)} is now a clean slate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(sys.argv[1:])))
