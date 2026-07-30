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


async def update_channel_identity(
    customer_id,
    *,
    whatsapp_number: str | None,
    normalized_number: str | None,
    number_verified: bool,
    profile_name_raw: str | None,
    resolved_name: str | None,
    name_source: str,
    name_confidence: float,
    name_requires_confirmation: bool,
) -> None:
    """Persist WhatsApp-channel identity (migration 000033).

    The phone fields and the raw profile name are always refreshed. The customer's
    NAME is only set from the WhatsApp profile when it has NOT been explicitly
    provided or confirmed — a CUSTOMER_PROVIDED / CONFIRMED name is never clobbered
    (so a WhatsApp profile change later can't overwrite the real name).
    """
    await database.execute(
        """
        update customers set
            whatsapp_number = coalesce($2, whatsapp_number),
            normalized_contact_number = coalesce($3, normalized_contact_number),
            contact_number_source = 'WHATSAPP_SENDER',
            contact_number_verified = $4,
            whatsapp_profile_name = coalesce($5, whatsapp_profile_name),
            customer_name = case
                when customer_name_source in ('CUSTOMER_PROVIDED','CONFIRMED') then customer_name
                else coalesce($6, customer_name) end,
            customer_name_source = case
                when customer_name_source in ('CUSTOMER_PROVIDED','CONFIRMED') then customer_name_source
                else $7 end,
            customer_name_confidence = case
                when customer_name_source in ('CUSTOMER_PROVIDED','CONFIRMED') then customer_name_confidence
                else $8 end,
            customer_name_requires_confirmation = case
                when customer_name_source in ('CUSTOMER_PROVIDED','CONFIRMED') then false
                else $9 end,
            updated_at = now()
        where id = $1
        """,
        customer_id, whatsapp_number, normalized_number, number_verified,
        profile_name_raw, resolved_name, name_source, name_confidence,
        name_requires_confirmation,
    )


async def set_customer_provided_name(customer_id, name: str) -> None:
    """Record a name the customer explicitly gave (CUSTOMER_PROVIDED) — highest
    precedence; the WhatsApp profile name is preserved separately in
    whatsapp_profile_name and never overrides this later."""
    await database.execute(
        "update customers set customer_name = $2, customer_name_source = 'CUSTOMER_PROVIDED', "
        "customer_name_confidence = 1.0, customer_name_requires_confirmation = false, "
        "display_name = $2, updated_at = now() where id = $1",
        customer_id, name,
    )


# Fields the WhatsApp capture flow may learn about a customer over the
# conversation. ``name`` maps to display_name; ``language`` to preferred_language.
# ``address`` is BACKEND-ONLY — never returned by the read APIs / broad tables.
_CUSTOMER_FIELD_COLUMNS = {
    "name": "display_name",
    "language": "preferred_language",
    "city": "city",
    "area": "area",
    "address": "address",
}


async def assign_ai_persona(customer_id: str, persona_id: str, persona_name: str,
                            version: int) -> dict | None:
    """Pin an approved AI persona to a customer ON FIRST CONTACT only.

    The UPDATE is CONDITIONAL (``where assigned_ai_persona_id is null``) so an
    already-assigned persona is NEVER overwritten — under two simultaneous first
    messages the first write wins and the second is a no-op; both then read the same
    persisted persona. Returns the current customer row (assigned either way)."""
    if not customer_id:
        return None
    await database.execute(
        """
        update customers
           set assigned_ai_persona_id       = $2,
               assigned_ai_persona_name      = $3,
               ai_persona_assigned_at        = now(),
               ai_persona_assignment_version = $4
         where id = $1 and assigned_ai_persona_id is null
        """,
        customer_id, persona_id, persona_name, int(version),
    )
    return await database.fetchrow("select * from customers where id = $1", customer_id)


async def update_customer_details(customer_id: str, fields: dict) -> dict | None:
    """Backfill customer-profile fields extracted from the conversation.

    Only non-empty values are written, and a value is only overwritten when the
    incoming value is genuinely new (so re-processing the same history is a
    no-op). ``fields`` uses the OrderDetails key names (name/language/city/area/
    address)."""
    sets: list[str] = []
    values: list = []
    for key, column in _CUSTOMER_FIELD_COLUMNS.items():
        value = fields.get(key)
        if value:
            values.append(value)
            sets.append(f"{column} = ${len(values)}")
    if not sets:
        return None
    values.append(customer_id)
    return await database.fetchrow(
        f"update customers set {', '.join(sets)} where id = ${len(values)} returning *",
        *values,
    )
