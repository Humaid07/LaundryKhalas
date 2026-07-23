"""Import the approved Laundry Khalas item catalogue into Supabase.

Reads ``config/laundry_catalogue.json`` (the reviewed structured seed data
transcribed from the approved price-list image) and upserts it into
``service_categories`` / ``services`` / ``service_items`` / ``service_aliases``,
recording the source + verification date. IDEMPOTENT: matches on the stable
``code`` / ``item_code`` so running it twice creates no duplicates; it updates
current values in place, appends a ``service_price_versions`` row ONLY when a
price actually changed, and DEACTIVATES catalogue items that are no longer in the
JSON (active=false) instead of deleting them — so historical orders that
reference them stay intact (task spec §11).

It never inserts customers, orders or conversations.

Usage (from apps/whatsapp-agent):
    python scripts/seed_service_catalogue.py            # apply migration DDL + seed
    python scripts/seed_service_catalogue.py --no-ddl   # seed only (tables must exist)

Guards: refuses to run against a production environment and requires
DATABASE_MODE=supabase (the catalogue tables live only in the Supabase schema).
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as _dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import database  # noqa: E402
from scripts._safety import _base_problems  # noqa: E402
from services import catalogue as cat  # noqa: E402
from settings import get_settings  # noqa: E402

_MIGRATION = (
    Path(__file__).resolve().parents[3]
    / "supabase" / "migrations" / "20260723_000007_service_catalogue.sql"
)
_SOURCE = "Approved Laundry Khalas price-list image"


async def _apply_ddl(conn) -> None:
    sql = _MIGRATION.read_text(encoding="utf-8")
    # asyncpg's execute runs a multi-statement script fine (no params here).
    await conn.execute(sql)
    print(f"  applied DDL: {_MIGRATION.name}")


async def _upsert_category(conn, c: dict, verified_at) -> str:
    row = await conn.fetchrow(
        """
        insert into service_categories (code, name, description, sort_order, active, source, source_verified_at)
        values ($1,$2,$3,$4,true,$5,$6)
        on conflict (code) do update set
            name=excluded.name, description=excluded.description,
            sort_order=excluded.sort_order, active=true,
            source=excluded.source, source_verified_at=excluded.source_verified_at
        returning id
        """,
        c["code"], c["name"], c.get("description"), c.get("sort_order", 0), _SOURCE, verified_at,
    )
    return row["id"]


async def _upsert_service(conn, s: dict, category_id: str, verified_at) -> str:
    row = await conn.fetchrow(
        """
        insert into services (category_id, code, name, sort_order, active, source, source_verified_at)
        values ($1,$2,$3,$4,true,$5,$6)
        on conflict (code) do update set
            category_id=excluded.category_id, name=excluded.name,
            sort_order=excluded.sort_order, active=true,
            source=excluded.source, source_verified_at=excluded.source_verified_at
        returning id
        """,
        category_id, s["code"], s["name"], s.get("sort_order", 0), _SOURCE, verified_at,
    )
    return row["id"]


async def _upsert_item(conn, item: dict, service_id: str, category_id: str,
                       verified_at, existing_prices: dict) -> tuple[str, bool]:
    """Upsert one item on a single connection. Returns (item_id, price_changed).
    ``existing_prices`` is the pre-fetched {item_code: (current, regular)} map so
    we avoid a per-item SELECT round-trip."""
    prev = existing_prices.get(item["item_code"])
    price_changed = (
        prev is None
        or prev[0] != item["current_price"]
        or prev[1] != item["regular_price"]
    )
    row = await conn.fetchrow(
        """
        insert into service_items (
            service_id, category_id, item_code, canonical_name, display_name, description,
            pricing_type, pricing_unit, current_price, regular_price, currency,
            is_starting_price, requires_inspection, requires_measurement, bag_limit_kg, note,
            active, sort_order, source, source_verified_at)
        values ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,true,$17,$18,$19)
        on conflict (item_code) do update set
            service_id=excluded.service_id, category_id=excluded.category_id,
            canonical_name=excluded.canonical_name, display_name=excluded.display_name,
            description=excluded.description, pricing_type=excluded.pricing_type,
            pricing_unit=excluded.pricing_unit, current_price=excluded.current_price,
            regular_price=excluded.regular_price, currency=excluded.currency,
            is_starting_price=excluded.is_starting_price, requires_inspection=excluded.requires_inspection,
            requires_measurement=excluded.requires_measurement, bag_limit_kg=excluded.bag_limit_kg,
            note=excluded.note, active=true, sort_order=excluded.sort_order,
            source=excluded.source, source_verified_at=excluded.source_verified_at
        returning id
        """,
        service_id, category_id, item["item_code"], item["canonical_name"],
        item.get("display_name"), item.get("description"), item["pricing_type"],
        item["pricing_unit"], item["current_price"], item["regular_price"], item["currency"],
        item["is_starting_price"], item["requires_inspection"], item["requires_measurement"],
        item.get("bag_limit_kg"), item.get("note"), item.get("sort_order", 0), _SOURCE, verified_at,
    )
    item_id = row["id"]
    if price_changed:
        await conn.execute(
            """
            insert into service_price_versions
                (item_code, current_price, regular_price, currency, pricing_type,
                 pricing_unit, source, source_verified_at)
            values ($1,$2,$3,$4,$5,$6,$7,$8)
            """,
            item["item_code"], item["current_price"], item["regular_price"], item["currency"],
            item["pricing_type"], item["pricing_unit"], _SOURCE, verified_at,
        )
    # Refresh aliases (delete + batched reinsert — idempotent, one round-trip).
    await conn.execute("delete from service_aliases where item_id = $1", item_id)
    aliases = sorted(set(item.get("aliases", []) + [item["canonical_name"].lower()]))
    if aliases:
        await conn.executemany(
            "insert into service_aliases (item_id, alias) values ($1,$2) on conflict do nothing",
            [(item_id, a) for a in aliases],
        )
    return item_id, price_changed


def _f(v):
    return None if v is None else float(v)


async def seed(conn, apply_ddl: bool) -> int:
    raw_verified = cat.meta().get("verified_at")
    verified_at = _dt.date.fromisoformat(raw_verified) if raw_verified else None

    if apply_ddl:
        await _apply_ddl(conn)

    # Pre-fetch existing prices in ONE query (avoids a per-item SELECT).
    existing_prices = {
        r["item_code"]: (_f(r["current_price"]), _f(r["regular_price"]))
        for r in await conn.fetch("select item_code, current_price, regular_price from service_items")
    }

    seen_codes: list[str] = []
    n_cat = n_svc = n_item = n_changed = 0
    for category in cat.categories():
        category_id = await _upsert_category(conn, category, verified_at)
        n_cat += 1
        for service in cat.services_for_category(category["code"]):
            service_id = await _upsert_service(conn, service, category_id, verified_at)
            n_svc += 1
            for item in cat.items_for_service(service["code"]):
                _, changed = await _upsert_item(conn, item, service_id, category_id,
                                                verified_at, existing_prices)
                seen_codes.append(item["item_code"])
                n_item += 1
                n_changed += int(changed)

    # Deactivate items that are in the DB but no longer in the JSON (never delete —
    # a historical order may reference them).
    deactivated = await conn.fetchval(
        "with d as (update service_items set active = false "
        "where active = true and item_code <> all($1::text[]) returning 1) "
        "select count(*) from d",
        seen_codes,
    )
    print(
        f"  categories={n_cat} services={n_svc} items={n_item} "
        f"price_versions_written={n_changed} deactivated={deactivated or 0}"
    )
    return n_item


async def _main(apply_ddl: bool) -> int:
    settings = get_settings()
    problems = _base_problems(settings)
    if problems:
        print("Refusing to seed the catalogue:")
        for p in problems:
            print(f"  - {p}")
        return 2
    print(
        f"Seeding Laundry Khalas catalogue into {settings.database_mode} "
        f"({settings.database_env}) — source: {_SOURCE}, verified {cat.meta().get('verified_at')}"
    )
    pool = await database.get_pool()
    try:
        # One warm connection + one transaction: far fewer round-trips over the
        # Supabase pooler, and the whole import is atomic.
        async with pool.acquire() as conn:
            async with conn.transaction():
                await seed(conn, apply_ddl)
    finally:
        await database.close_pool()
    print("Done. DB is the runtime source of truth; run test_catalogue_pricing to verify parity.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Seed the Laundry Khalas item catalogue into Supabase.")
    ap.add_argument("--no-ddl", action="store_true", help="Skip applying the migration DDL (tables must already exist).")
    args = ap.parse_args()
    raise SystemExit(asyncio.run(_main(apply_ddl=not args.no_ddl)))
