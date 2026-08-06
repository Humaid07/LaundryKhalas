"""Facility "details reviewed" acknowledgement persistence (asyncpg / Supabase).

Records that a facility user reviewed an order's details, notes and photos before
processing, stamped with the version signals in effect at that moment. A later
critical note / photo / amendment bumps a version, so the stored acknowledgement
no longer matches current content and the facility must re-acknowledge (the
freshness comparison itself is the pure ``facility_order_view.build_review_ack``).

Every read/write is SCOPED to the caller's facility_id — the same isolation
boundary as the other facility repos (the service role bypasses RLS).
"""
from __future__ import annotations

from db import database

_COLS = (
    "id, order_id, facility_id, facility_user_id, order_version, notes_version, "
    "photo_version, acknowledged_at, invalidated_at, invalidation_reason, "
    "created_at, updated_at"
)


def to_read(row: dict | None) -> dict | None:
    if not row:
        return None
    return {
        "id": str(row["id"]),
        "order_id": str(row["order_id"]) if row.get("order_id") else None,
        "facility_id": str(row["facility_id"]) if row.get("facility_id") else None,
        "facility_user_id": row.get("facility_user_id"),
        "order_version": int(row.get("order_version") or 0),
        "notes_version": int(row.get("notes_version") or 0),
        "photo_version": int(row.get("photo_version") or 0),
        "acknowledged_at": row.get("acknowledged_at"),
        "invalidated_at": row.get("invalidated_at"),
        "invalidation_reason": row.get("invalidation_reason"),
    }


async def latest_for_order(facility_id: str, order_uuid: str) -> dict | None:
    """The most recent acknowledgement for (facility, order), or None. Scoped."""
    row = await database.fetchrow(
        f"select {_COLS} from facility_order_reviews "
        "where facility_id = $1 and order_id = $2 "
        "order by acknowledged_at desc limit 1",
        facility_id, order_uuid,
    )
    return to_read(row)


async def acknowledge(
    *,
    facility_id: str,
    order_uuid: str,
    facility_user_id: str | None,
    order_version: int,
    notes_version: int,
    photo_version: int,
) -> dict | None:
    """Insert a fresh acknowledgement row stamped with the current versions.

    Idempotent-by-content: if the latest live acknowledgement already matches
    these exact versions, no new row is written and the existing one is returned
    (so a double-click or retried request never stacks duplicate acknowledgements).
    """
    existing = await latest_for_order(facility_id, order_uuid)
    if (
        existing
        and not existing.get("invalidated_at")
        and existing["order_version"] == int(order_version)
        and existing["notes_version"] == int(notes_version)
        and existing["photo_version"] == int(photo_version)
    ):
        return existing
    row = await database.fetchrow(
        f"""
        insert into facility_order_reviews
            (order_id, facility_id, facility_user_id, order_version, notes_version,
             photo_version, is_test_data, is_demo, environment)
        values ($1, $2, $3, $4, $5, $6, false, false, 'dev')
        returning {_COLS}
        """,
        order_uuid, facility_id, facility_user_id,
        int(order_version), int(notes_version), int(photo_version),
    )
    return to_read(row)


async def invalidate_for_order(order_uuid: str, reason: str) -> int:
    """Explicitly mark all live acknowledgements for an order outdated (e.g. when a
    CRITICAL note or amendment is added). Returns the number of rows invalidated.
    Not facility-scoped — an order belongs to one facility, and the caller is an
    internal/agent write path. Best-effort; never the primary freshness signal
    (version mismatch already invalidates)."""
    result = await database.execute(
        "update facility_order_reviews set invalidated_at = now(), "
        "invalidation_reason = $2, updated_at = now() "
        "where order_id = $1 and invalidated_at is null",
        order_uuid, reason,
    )
    try:
        return int(str(result).split()[-1])
    except (ValueError, IndexError):
        return 0
