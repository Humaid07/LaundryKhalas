"""Facility notification log + notification contacts (dev/test Supabase schema).

The notification SERVICE (services/facility_notifications.py) is mock-first +
env-gated: by default it only LOGS a row here (status='mock_logged') and never
sends externally. Notifications never contain full customer address/phone.
Every read/write is scoped by ``facility_id``.
"""
from __future__ import annotations

from services.privacy import mask_phone
from db import database

_SELECT = """
  select id, facility_id, order_id, order_ref, issue_id, type, channel,
         destination_masked, status, message_preview, provider, provider_message_id,
         error, read_at, dedupe_key, created_at, sent_at
    from facility_notifications
"""


async def create(
    *,
    facility_id: str,
    type: str,
    order_uuid: str | None = None,
    order_ref: str | None = None,
    issue_uuid: str | None = None,
    channel: str = "mock",
    destination_masked: str | None = None,
    status: str = "mock_logged",
    message_preview: str | None = None,
    dedupe_key: str | None = None,
) -> dict | None:
    # DB-enforced idempotency: (facility_id, dedupe_key) is uniquely indexed, so a
    # racing duplicate is silently ignored rather than raising.
    return await database.fetchrow(
        """
        insert into facility_notifications
            (facility_id, order_id, order_ref, issue_id, type, channel, destination_masked,
             status, message_preview, dedupe_key, is_test_data, is_demo, environment, created_by_seed)
        values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, true, false, 'dev', false)
        on conflict (facility_id, dedupe_key) where dedupe_key is not null do nothing
        returning id, facility_id, order_id, order_ref, issue_id, type, channel,
                  destination_masked, status, message_preview, dedupe_key, read_at,
                  created_at, sent_at
        """,
        facility_id, order_uuid, order_ref, issue_uuid, type, channel,
        destination_masked, status, message_preview, dedupe_key,
    )


async def exists_for_order(facility_id: str, order_uuid: str, type: str) -> bool:
    return bool(await database.fetchval(
        "select 1 from facility_notifications "
        "where facility_id = $1 and order_id = $2 and type = $3 limit 1",
        facility_id, order_uuid, type,
    ))


async def exists_by_dedupe(facility_id: str, dedupe_key: str) -> bool:
    return bool(await database.fetchval(
        "select 1 from facility_notifications "
        "where facility_id = $1 and dedupe_key = $2 limit 1",
        facility_id, dedupe_key,
    ))


async def list_for_facility(facility_id: str, *, unread_only: bool = False, limit: int = 50) -> list[dict]:
    if unread_only:
        return await database.fetch(
            _SELECT + " where facility_id = $1 and read_at is null "
            "order by created_at desc limit $2",
            facility_id, max(1, min(int(limit), 200)),
        )
    return await database.fetch(
        _SELECT + " where facility_id = $1 order by created_at desc limit $2",
        facility_id, max(1, min(int(limit), 200)),
    )


async def mark_read(facility_id: str, notification_id: str) -> dict | None:
    return await database.fetchrow(
        "update facility_notifications set read_at = now() "
        "where id = $1 and facility_id = $2 and read_at is null "
        "returning id, facility_id, type, status, read_at, created_at",
        notification_id, facility_id,
    )


async def unread_count(facility_id: str) -> int:
    return await database.fetchval(
        "select count(*) from facility_notifications "
        "where facility_id = $1 and read_at is null",
        facility_id,
    ) or 0


# --- contacts sub-API ------------------------------------------------------
_CONTACT_SELECT = """
  select id, facility_id, name, role, mobile_masked, notification_types, active,
         created_at, updated_at
    from facility_notification_contacts
"""


async def list_contacts(facility_id: str) -> list[dict]:
    """Contacts for a facility — full mobile_e164 is NEVER returned (masked only)."""
    return await database.fetch(
        _CONTACT_SELECT + " where facility_id = $1 order by created_at asc", facility_id
    )


async def add_contact(
    facility_id: str,
    *,
    name: str,
    mobile_e164: str,
    role: str | None = None,
    notification_types: list[str] | None = None,
    active: bool = True,
) -> dict | None:
    return await database.fetchrow(
        """
        insert into facility_notification_contacts
            (facility_id, name, role, mobile_e164, mobile_masked, notification_types,
             active, is_test_data, is_demo, environment, created_by_seed)
        values ($1, $2, $3, $4, $5, $6::text[], $7, true, false, 'dev', false)
        returning id, facility_id, name, role, mobile_masked, notification_types,
                  active, created_at, updated_at
        """,
        facility_id, name, role, mobile_e164, mask_phone(mobile_e164),
        list(notification_types or []), active,
    )


async def update_contact(
    facility_id: str,
    contact_id: str,
    *,
    name: str | None = None,
    role: str | None = None,
    mobile_e164: str | None = None,
    notification_types: list[str] | None = None,
    active: bool | None = None,
) -> dict | None:
    sets: list[str] = []
    params: list = [contact_id, facility_id]

    def st(col, val, cast=""):
        params.append(val)
        sets.append(f"{col} = ${len(params)}{cast}")

    if name is not None:
        st("name", name)
    if role is not None:
        st("role", role)
    if mobile_e164 is not None:
        st("mobile_e164", mobile_e164)
        st("mobile_masked", mask_phone(mobile_e164))
    if notification_types is not None:
        st("notification_types", list(notification_types), "::text[]")
    if active is not None:
        st("active", active)
    if not sets:
        return await database.fetchrow(
            _CONTACT_SELECT + " where id = $1 and facility_id = $2", contact_id, facility_id
        )
    return await database.fetchrow(
        f"update facility_notification_contacts set {', '.join(sets)} "
        "where id = $1 and facility_id = $2 "
        "returning id, facility_id, name, role, mobile_masked, notification_types, "
        "active, created_at, updated_at",
        *params,
    )
