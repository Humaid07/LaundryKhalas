"""Verify migration 000033 applied cleanly to the dev/test Supabase project.

Checks: order_notes table + its columns/constraints/indexes/RLS policy, and the
new columns on conversations/orders/customers. Ends with an order_notes insert
round-trip inside a transaction that is ALWAYS rolled back (no data written).

Usage (from apps/whatsapp-agent, DATABASE_MODE=supabase, DATABASE_ENV=test):
    python scripts/verify_voice_notes_location_identity.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import database  # noqa: E402
from settings import get_settings  # noqa: E402

_CONVO_COLS = [
    "unprocessed_voice_message_count", "last_unprocessed_voice_message_id",
    "last_unprocessed_voice_message_at", "voice_text_fallback_sent_at", "voice_escalation_status",
]
_ORDER_COLS = [
    "building_name", "villa_number", "apartment_number", "floor", "room_number", "landmark",
    "access_details", "location_source", "location_type", "location_message_id",
    "location_received_at", "location_accuracy", "location_pin_status",
    "confirmed_notes_snapshot", "notes_confirmed_at", "facility_handoff_status",
    "facility_handoff_at", "facility_handoff_attempts", "facility_handoff_payload",
]
_CUSTOMER_COLS = [
    "whatsapp_number", "normalized_contact_number", "contact_number_source",
    "contact_number_verified", "whatsapp_profile_name", "customer_name",
    "customer_name_source", "customer_name_confidence", "customer_name_requires_confirmation",
]
_NOTE_COLS = [
    "id", "order_id", "conversation_id", "category", "text", "source", "source_message_id",
    "confidence", "status", "customer_confirmed", "is_amendment", "dedupe_key", "superseded_by",
]


async def _cols(table: str) -> set[str]:
    rows = await database.fetch(
        "select column_name from information_schema.columns where table_name = $1", table
    )
    return {r["column_name"] for r in rows}


async def _main() -> int:
    settings = get_settings()
    if settings.database_mode != "supabase":
        print(f"DATABASE_MODE={settings.database_mode}; set it to 'supabase' to verify.")
        return 2

    ok = True
    reg = await database.fetchval("select to_regclass('public.order_notes')")
    print(f"order_notes table: {'OK' if reg else 'MISSING'}")
    ok = ok and bool(reg)

    for table, wanted in (("conversations", _CONVO_COLS), ("orders", _ORDER_COLS),
                          ("customers", _CUSTOMER_COLS), ("order_notes", _NOTE_COLS)):
        have = await _cols(table)
        missing = [c for c in wanted if c not in have]
        print(f"{table}: {'OK' if not missing else 'MISSING ' + ', '.join(missing)}")
        ok = ok and not missing

    idx = await database.fetch("select indexname from pg_indexes where tablename = 'order_notes'")
    names = {r["indexname"] for r in idx}
    for want in ("uq_order_notes_active_dedupe", "idx_order_notes_order"):
        print(f"index {want}: {'OK' if want in names else 'MISSING'}")
        ok = ok and want in names

    pol = await database.fetch("select policyname from pg_policies where tablename = 'order_notes'")
    has_policy = any(r["policyname"] == "order_notes_no_public_access" for r in pol)
    print(f"RLS policy order_notes_no_public_access: {'OK' if has_policy else 'MISSING'}")
    ok = ok and has_policy

    # Insert round-trip, always rolled back.
    pool = await database.get_pool()
    try:
        async with pool.acquire() as conn:
            tr = conn.transaction()
            await tr.start()
            try:
                oid = await conn.fetchval("select id from orders limit 1")
                if oid:
                    await conn.execute(
                        "insert into order_notes (order_id, category, text, dedupe_key, is_test_data) "
                        "values ($1, 'PICKUP_INSTRUCTION', 'verify roundtrip', 'verify-key', true)",
                        oid,
                    )
                    print("insert round-trip: OK (rolled back)")
                else:
                    print("insert round-trip: SKIPPED (no orders row)")
            finally:
                await tr.rollback()
    finally:
        await database.close_pool()

    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
