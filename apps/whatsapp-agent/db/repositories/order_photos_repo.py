"""Facility order-photo metadata reads/writes against the dev/test Supabase.

The image BYTES live in storage (local dev folder or, later, a cloud provider);
this repo only persists the row that locates and describes each file. Every row
carries both ``order_id`` (orders UUID FK) and ``facility_id`` so reads/writes
stay scoped to the caller's facility — the same isolation boundary as
``facility_orders_repo`` (the service role bypasses RLS, so the app enforces it).

``to_read`` is PII-SAFE: it exposes only the photo's own operational metadata
(stage, generated file name, size, uploader LABEL, timestamps). It never returns
the raw storage key, the uploader's user id, or any customer field — file names
are generated (``order-photo-<uuid>.<ext>``) and never contain customer data.
"""
from __future__ import annotations

from db import database

# Stages the product implements today (the API rejects anything else).
STAGES = ("intake", "pre_dispatch")

_SELECT_COLS = (
    "id, order_id, facility_id, stage, storage_provider, storage_key, public_url, "
    "file_name, content_type, file_size, uploaded_by_user_id, uploaded_by_name, "
    "metadata, created_at, deleted_at"
)


def to_read(row: dict) -> dict:
    """PII-safe API view of one photo row. No storage_key / user id / customer data."""
    return {
        "id": str(row["id"]),
        "stage": row.get("stage"),
        "file_name": row.get("file_name"),
        "content_type": row.get("content_type"),
        "file_size": row.get("file_size"),
        "uploaded_by": row.get("uploaded_by_name"),
        # public_url is set only for a public cloud provider; for local storage it
        # is null and the client fetches bytes via the scoped content endpoint.
        "url": row.get("public_url"),
        "created_at": row.get("created_at"),
    }


async def create(
    *,
    order_uuid: str,
    facility_id: str,
    stage: str,
    storage_provider: str,
    storage_key: str,
    file_name: str,
    content_type: str,
    file_size: int,
    public_url: str | None = None,
    uploaded_by_user_id: str | None = None,
    uploaded_by_name: str | None = None,
    metadata: dict | None = None,
    is_test_data: bool = True,
    seed_source: str | None = None,
    created_by_seed: bool = False,
) -> dict | None:
    return await database.fetchrow(
        f"""
        insert into order_photos
            (order_id, facility_id, stage, storage_provider, storage_key, public_url,
             file_name, content_type, file_size, uploaded_by_user_id, uploaded_by_name,
             metadata, is_test_data, is_demo, environment, seed_source, created_by_seed)
        values ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12::jsonb,
                $13, false, 'dev', $14, $15)
        returning {_SELECT_COLS}
        """,
        order_uuid,
        facility_id,
        stage,
        storage_provider,
        storage_key,
        public_url,
        file_name,
        content_type,
        int(file_size),
        uploaded_by_user_id,
        uploaded_by_name,
        metadata or {},
        is_test_data,
        seed_source,
        created_by_seed,
    )


async def list_for_order(order_uuid: str, *, stage: str | None = None) -> list[dict]:
    """Non-deleted photos for an order (optionally one stage), oldest first. The
    caller must have already resolved ``order_uuid`` via the facility-scoped order
    lookup, so this is only ever reached for the facility's own order."""
    if stage:
        return await database.fetch(
            f"select {_SELECT_COLS} from order_photos "
            "where order_id = $1 and stage = $2 and deleted_at is null "
            "order by created_at asc",
            order_uuid, stage,
        )
    return await database.fetch(
        f"select {_SELECT_COLS} from order_photos "
        "where order_id = $1 and deleted_at is null order by created_at asc",
        order_uuid,
    )


async def count_for_stage(order_uuid: str, stage: str) -> int:
    """Live (non-deleted) photo count for an order+stage — enforces the per-stage cap."""
    return int(await database.fetchval(
        "select count(*) from order_photos "
        "where order_id = $1 and stage = $2 and deleted_at is null",
        order_uuid, stage,
    ) or 0)


async def get(photo_id: str, facility_id: str) -> dict | None:
    """One non-deleted photo by id, SCOPED to the facility. None if not the
    facility's — a mismatched facility is indistinguishable from missing."""
    return await database.fetchrow(
        f"select {_SELECT_COLS} from order_photos "
        "where id = $1 and facility_id = $2 and deleted_at is null",
        photo_id, facility_id,
    )


async def soft_delete(photo_id: str, facility_id: str) -> dict | None:
    """Soft-delete (never hard-delete evidence), SCOPED to the facility. Returns
    the row when it was this facility's live photo, else None."""
    return await database.fetchrow(
        f"update order_photos set deleted_at = now() "
        "where id = $1 and facility_id = $2 and deleted_at is null "
        f"returning {_SELECT_COLS}",
        photo_id, facility_id,
    )


async def counts_for_orders(order_uuids: list[str]) -> dict[str, dict[str, int]]:
    """Per-order live photo counts by stage for the order-list badges — ONE
    grouped query for the whole page (no N+1). Returns
    ``{order_uuid: {"intake": n, "pre_dispatch": n}}`` for orders that have any."""
    if not order_uuids:
        return {}
    rows = await database.fetch(
        "select order_id, stage, count(*) as n from order_photos "
        "where order_id = any($1::uuid[]) and deleted_at is null "
        "group by order_id, stage",
        order_uuids,
    )
    out: dict[str, dict[str, int]] = {}
    for r in rows:
        oid = str(r["order_id"])
        out.setdefault(oid, {})[r["stage"]] = int(r["n"])
    return out
