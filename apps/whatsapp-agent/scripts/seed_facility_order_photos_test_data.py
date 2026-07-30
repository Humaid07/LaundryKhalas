"""Seed development/test orders for the Facility order-photo feature.

Creates three clearly-flagged TEST orders (LK-TEST-FAC-001..003) scoped to the
dev facility so the intake / pre-dispatch upload flow can be exercised end-to-end
in the partner dashboard, plus the pre-existing intake photos the spec describes
(002 → 2 intake, 003 → 1 intake). All rows carry the standard test-data markers
(is_test_data=true, seed_source) so they are unmistakably development data and
are swept by the reset scripts.

Idempotent + guarded by ALLOW_TEST_SEED (and the dev/test-only _safety guard).
No customer PII is stored — customer_name is a neutral placeholder and the photo
files are generated (order-photo-<uuid>.jpg).

Run:  python -m scripts.seed_facility_order_photos_test_data   (from apps/whatsapp-agent)
"""
from __future__ import annotations

import asyncio
import base64
from datetime import date
from pathlib import Path
from uuid import uuid4

from db import database
from scripts._safety import check_seed_allowed
from settings import get_settings

SEED_SOURCE = "facility_order_photo_seed"
_STORAGE_ROOT = Path(__file__).resolve().parents[1] / "storage" / "order-photos"

# A valid 1x1 JPEG (magic FF D8 FF …) so seeded thumbnails render + pass the
# server's magic-byte check. Real proof photos are uploaded through the UI.
_PLACEHOLDER_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRof"
    "Hh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwh"
    "MjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAAR"
    "CAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAf/xAAUEAEAAAAAAAAAAAAA"
    "AAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oA"
    "DAMBAAIRAxEAPwCdABmX/9k="
)

# order_id → (service label, service_id, status, area, intake photo count)
_TEST_ORDERS = [
    ("LK-TEST-FAC-001", "Pant Alteration — Shorten Length", "pant_alteration",
     "picked_up", "Dubai Marina", 0),
    ("LK-TEST-FAC-002", "Boutique Clean & Press", "boutique_clean_press",
     "in_cleaning", "JLT", 2),
    ("LK-TEST-FAC-003", "Carpet Cleaning", "carpet_cleaning",
     "ready_for_delivery", "Al Barsha", 1),
]


async def _dev_facility_id() -> str | None:
    settings = get_settings()
    if settings.facility_dev_id:
        return settings.facility_dev_id
    return await database.fetchval(
        "select id::text from facilities where is_active order by created_at asc limit 1"
    )


async def _existing_order_columns() -> set[str]:
    rows = await database.fetch(
        "select column_name from information_schema.columns where table_name = 'orders'")
    return {r["column_name"] for r in rows}


async def _upsert_order(cols: set[str], order_id: str, service: str, service_id: str,
                        status: str, area: str, facility_id: str) -> str:
    """Upsert one test order (only columns that exist), returning its UUID."""
    # Candidate values — filtered to columns that actually exist in this schema.
    candidate = {
        "order_id": order_id,
        "facility_id": facility_id,
        "customer_name": "Test Customer",   # neutral placeholder, never real PII
        "service": service,
        "service_display_name": service,
        "service_id": service_id,
        "status": status,
        "area": area,
        "pickup_area": area,
        "pickup_emirate": "Dubai",
        "city": "Dubai",
        "pickup_slot": "9:00 AM – 12:00 PM",
        "pickup_date": date.today(),         # today → visible under the default range
        "amount": 120,
        "source_channel": "seed",
        "is_test_data": True,
        "is_demo": False,
        "environment": "dev",
        "seed_source": SEED_SOURCE,
        "created_by_seed": True,
    }
    data = {k: v for k, v in candidate.items() if k in cols}
    keys = list(data.keys())
    placeholders = [f"${i + 1}" for i in range(len(keys))]
    updates = ", ".join(f"{k} = excluded.{k}" for k in keys if k != "order_id")
    sql = (
        f"insert into orders ({', '.join(keys)}) values ({', '.join(placeholders)}) "
        f"on conflict (order_id) do update set {updates} "
        "returning id::text"
    )
    return await database.fetchval(sql, *[data[k] for k in keys])


async def _seed_photos(order_uuid: str, facility_id: str, count: int) -> None:
    """Replace this order's seeded intake photos with exactly `count` fresh rows +
    files (idempotent: re-running yields the same count, no duplicates)."""
    # Remove any prior seeded rows for this order so counts stay exact on re-run.
    await database.execute(
        "delete from order_photos where order_id = $1 and seed_source = $2",
        order_uuid, SEED_SOURCE,
    )
    dest_dir = _STORAGE_ROOT / order_uuid
    dest_dir.mkdir(parents=True, exist_ok=True)
    for _ in range(count):
        file_name = f"order-photo-{uuid4().hex}.jpg"
        storage_key = f"{order_uuid}/{file_name}"
        (_STORAGE_ROOT / storage_key).write_bytes(_PLACEHOLDER_JPEG)
        await database.execute(
            "insert into order_photos "
            "(order_id, facility_id, stage, storage_provider, storage_key, file_name, "
            " content_type, file_size, uploaded_by_name, metadata, is_test_data, "
            " environment, seed_source, created_by_seed) "
            "values ($1,$2,'intake','local',$3,$4,'image/jpeg',$5,'Facility Seed',"
            " $6::jsonb, true, 'dev', $7, true)",
            order_uuid, facility_id, storage_key, file_name, len(_PLACEHOLDER_JPEG),
            {"stage": "intake", "seeded": True}, SEED_SOURCE,
        )
    if count:
        # One audit event so the order timeline reflects the seeded intake batch.
        await database.execute(
            "insert into order_events (order_id, event_type, actor_type, actor_name, "
            " notes, metadata, is_test_data, environment, seed_source, created_by_seed) "
            "values ($1,'intake_photos_uploaded','facility','Facility Seed',"
            " $2, $3::jsonb, true, 'dev', $4, true)",
            order_uuid, f"{count} intake photo(s) seeded for testing.",
            {"photo_count": count, "stage": "intake", "seeded": True}, SEED_SOURCE,
        )


async def seed() -> None:
    settings = get_settings()
    problems = check_seed_allowed(settings)
    if problems:
        print("SKIP: refusing to seed —")
        for p in problems:
            print(f"  - {p}")
        return

    facility_id = await _dev_facility_id()
    if not facility_id:
        print("ERROR: no active facility found — run the facility migrations/seed first.")
        return

    cols = await _existing_order_columns()
    print(f"Seeding facility order-photo test data -> facility {facility_id}")
    for order_id, service, service_id, status, area, intake in _TEST_ORDERS:
        order_uuid = await _upsert_order(cols, order_id, service, service_id, status, area, facility_id)
        await _seed_photos(order_uuid, facility_id, intake)
        print(f"  {order_id}: {status:20} {area:14} intake={intake}  (uuid={order_uuid})")
    print("Done. These are development/test orders (is_test_data=true, seed_source="
          f"'{SEED_SOURCE}').")


if __name__ == "__main__":
    asyncio.run(seed())
