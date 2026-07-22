"""Expire stale WhatsApp order drafts: DRAFT -> ABANDONED (spec §29).

Safe + idempotent: only touches rows still in status 'draft' whose created_at is
older than DRAFT_EXPIRY_HOURS. Confirmed/active/terminal orders are never touched.
Writes an ORDER_ABANDONED order_event per expired draft. Never deletes anything.

Run manually or from a scheduler (cron / Celery beat):
    python scripts/expire_drafts.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import database  # noqa: E402
from services import order_store  # noqa: E402
from settings import get_settings  # noqa: E402


async def expire_drafts() -> int:
    """Mark expired drafts abandoned. Returns the number expired."""
    hours = max(1, get_settings().draft_expiry_hours)
    rows = await database.fetch(
        """
        update orders
           set status = $1, conversation_state = 'booking_expired'
         where status = $2
           and created_at < now() - ($3 || ' hours')::interval
        returning id, order_id
        """,
        order_store.ABANDONED, order_store.DRAFT, str(hours),
    )
    for r in rows:
        await database.execute(
            """
            insert into order_events
                (order_id, event_type, from_status, to_status, actor_type, notes,
                 is_test_data, is_demo, environment, created_by_seed)
            values ($1, 'ORDER_ABANDONED', $2, $3, 'system',
                    'Draft expired after inactivity.', false, false, 'dev', false)
            """,
            r["id"], order_store.DRAFT, order_store.ABANDONED,
        )
    return len(rows)


async def main() -> int:
    if not database.is_supabase_mode():
        print("[skip] draft expiry runs against Supabase only (DATABASE_MODE=supabase).")
        return 0
    n = await expire_drafts()
    print(f"[ok] expired {n} stale draft(s) -> abandoned "
          f"(> {get_settings().draft_expiry_hours}h old).")
    await database.close_pool()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
