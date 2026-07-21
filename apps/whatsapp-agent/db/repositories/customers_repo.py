"""Customer upsert against the dev/test Supabase schema.

Used by the inbound Evolution webhook to attach a real WhatsApp sender to a
conversation. The full number is stored only in ``phone_e164`` (backend-only,
needed to send a reply); ``masked_phone`` + ``phone_hash`` are what everything
else uses. Real inbound rows are is_test_data=false / created_by_seed=false, so
the seed-reset script never touches them.
"""
from __future__ import annotations

from db import database
from services.privacy import hash_phone, mask_phone


async def get_or_create_by_phone(
    phone_e164: str, display_name: str | None = None, channel: str = "whatsapp"
) -> dict:
    phash = hash_phone(phone_e164)
    existing = await database.fetchrow(
        "select * from customers where phone_hash = $1 order by created_at asc limit 1", phash
    )
    if existing:
        # Backfill a name once we learn it (Evolution pushName), if missing.
        if display_name and not existing.get("display_name"):
            await database.execute(
                "update customers set display_name = $2 where id = $1",
                existing["id"],
                display_name,
            )
            existing["display_name"] = display_name
        return existing

    return await database.fetchrow(
        """
        insert into customers
            (display_name, phone_e164, phone_hash, masked_phone, source_channel,
             is_test_data, is_demo, environment, created_by_seed)
        values ($1, $2, $3, $4, $5, false, false, 'dev', false)
        returning *
        """,
        display_name or "WhatsApp Customer",
        phone_e164,
        phash,
        mask_phone(phone_e164),
        channel,
    )
