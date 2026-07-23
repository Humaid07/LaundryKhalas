"""Scoped clear: cancel any IN-PROGRESS draft on a single WhatsApp conversation
so a manual test starts a fresh booking. Touches ONLY the conversation whose
external_id is evo:<E164>. Safe on the test Supabase project.

Usage:  python -m scripts.clear_draft_for_number +971543216640
"""
import asyncio
import sys

from db import database
from db.repositories import orders_repo


async def _run(e164: str) -> None:
    external_id = f"evo:{e164}"
    if not database.is_supabase_mode():
        print("Not in supabase mode — nothing to do.")
        return

    convo = await database.fetchrow(
        "select id from conversations where external_conversation_id = $1", external_id
    )
    if not convo:
        print(f"No conversation found for {external_id}.")
        return

    draft = await orders_repo.get_active_draft(convo["id"])
    if not draft:
        print(f"No active draft on {external_id} — already clean.")
        return

    print(f"Cancelling draft {draft.get('order_id')} "
          f"(state={draft.get('conversation_state')}) on {external_id} …")
    row = await orders_repo.cancel_booking(draft["id"])
    print(f"Done. Order {row.get('order_id')} -> status={row.get('status')}, "
          f"state={row.get('conversation_state')}")

    # sanity: confirm no active draft remains
    remaining = await orders_repo.get_active_draft(convo["id"])
    print("Active draft remaining:", remaining is not None)


async def main(e164: str) -> None:
    try:
        await _run(e164)
    finally:
        await database.close_pool()  # same loop as the pool was created in


if __name__ == "__main__":
    number = sys.argv[1] if len(sys.argv) > 1 else "+971543216640"
    asyncio.run(main(number))
