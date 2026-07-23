"""Read access to the item-level service catalogue (dev/test Supabase schema).

The catalogue APIs (task spec §12) read the catalogue from PostgreSQL/Supabase —
the runtime source of truth — via this repo. When the process is not in supabase
mode, or the catalogue tables are not seeded yet, it transparently falls back to
the same cached JSON accessor the agent uses (``services.catalogue``), so the
APIs, agent and tests always return identical data. ``sync_status`` compares the
DB against the JSON so drift is observable (like the service-taxonomy check).
"""
from __future__ import annotations

from db import database
from services import catalogue as cat


async def _db_available() -> bool:
    if not database.is_supabase_mode():
        return False
    try:
        n = await database.fetchval(
            "select count(*) from service_items where active = true"
        )
        return bool(n and n > 0)
    except Exception:  # noqa: BLE001 - table missing / not seeded / offline
        return False


def _row_to_item(row: dict) -> dict:
    return {
        "item_code": row["item_code"],
        "code": row["item_code"],
        "category_code": row.get("category_code"),
        "category_name": row.get("category_name"),
        "service_code": row.get("service_code"),
        "service_name": row.get("service_name"),
        "canonical_name": row["canonical_name"],
        "display_name": row.get("display_name") or row["canonical_name"],
        "name": row["canonical_name"],
        "description": row.get("description"),
        "pricing_type": row["pricing_type"],
        "pricing_unit": row["pricing_unit"],
        "current_price": float(row["current_price"]) if row.get("current_price") is not None else None,
        "regular_price": float(row["regular_price"]) if row.get("regular_price") is not None else None,
        "currency": row.get("currency") or "AED",
        "is_starting_price": bool(row.get("is_starting_price")),
        "requires_inspection": bool(row.get("requires_inspection")),
        "requires_measurement": bool(row.get("requires_measurement")),
        "bag_limit_kg": float(row["bag_limit_kg"]) if row.get("bag_limit_kg") is not None else None,
        "note": row.get("note"),
        "active": bool(row.get("active", True)),
        "sort_order": row.get("sort_order", 0),
        "source": row.get("source"),
    }


async def list_categories() -> list[dict]:
    if await _db_available():
        rows = await database.fetch(
            "select code, name, description, sort_order from service_categories "
            "where active = true order by sort_order, name"
        )
        return [dict(r) for r in rows]
    return [
        {"code": c["code"], "name": c["name"], "description": c.get("description"),
         "sort_order": c.get("sort_order", 0)}
        for c in cat.categories()
    ]


async def list_items(category_code: str | None = None) -> list[dict]:
    if await _db_available():
        sql = (
            "select i.*, c.code as category_code, c.name as category_name, "
            "s.code as service_code, s.name as service_name "
            "from service_items i "
            "left join service_categories c on c.id = i.category_id "
            "left join services s on s.id = i.service_id "
            "where i.active = true"
        )
        params: list = []
        if category_code:
            params.append(category_code)
            sql += f" and c.code = ${len(params)}"
        sql += " order by c.sort_order, s.sort_order, i.sort_order, i.canonical_name"
        rows = await database.fetch(sql, *params)
        return [_row_to_item(r) for r in rows]
    items = cat.all_items()
    if category_code:
        items = [i for i in items if i["category_code"] == category_code]
    return items


async def get_item(item_code: str) -> dict | None:
    if await _db_available():
        row = await database.fetchrow(
            "select i.*, c.code as category_code, c.name as category_name, "
            "s.code as service_code, s.name as service_name "
            "from service_items i "
            "left join service_categories c on c.id = i.category_id "
            "left join services s on s.id = i.service_id "
            "where i.item_code = $1",
            item_code,
        )
        return _row_to_item(row) if row else None
    return cat.item_by_code(item_code)


async def sync_status() -> dict:
    """Compare the DB catalogue to the JSON seed. ``in_sync`` is True when every
    active JSON item exists in the DB with the same current price."""
    json_items = {i["item_code"]: i for i in cat.all_items()}
    if not await _db_available():
        return {
            "db_available": False,
            "source": "json",
            "categories": len(cat.categories()),
            "items": len(json_items),
            "in_sync": True,
            "mismatches": [],
        }
    rows = await database.fetch(
        "select item_code, current_price from service_items where active = true"
    )
    db_prices = {r["item_code"]: (float(r["current_price"]) if r["current_price"] is not None else None)
                 for r in rows}
    mismatches: list[str] = []
    for code, item in json_items.items():
        if code not in db_prices:
            mismatches.append(f"missing in DB: {code}")
        elif db_prices[code] != item["current_price"]:
            mismatches.append(
                f"price drift {code}: db={db_prices[code]} json={item['current_price']}"
            )
    for code in db_prices:
        if code not in json_items:
            mismatches.append(f"active in DB but not in JSON: {code}")
    return {
        "db_available": True,
        "source": "supabase",
        "categories": len(cat.categories()),
        "items": len(db_prices),
        "in_sync": not mismatches,
        "mismatches": mismatches[:50],
    }
