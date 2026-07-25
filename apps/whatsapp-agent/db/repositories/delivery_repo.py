"""Delivery SLA rule reads + order delivery-estimate snapshot (dev/test Supabase).

Reads the SLA rules from the DB (runtime source of truth; JSON fallback when not
seeded), and freezes the computed delivery estimate onto a confirmed order so it
never changes when the SLA rules change later (task spec §§25/27).
"""
from __future__ import annotations

from db import database
from services import delivery


async def _db_available() -> bool:
    if not database.is_supabase_mode():
        return False
    try:
        n = await database.fetchval("select count(*) from delivery_sla_rules where active")
        return bool(n and n > 0)
    except Exception:  # noqa: BLE001 - table missing / not seeded / offline
        return False


async def list_rules() -> list[dict]:
    if await _db_available():
        rows = await database.fetch(
            "select code, match_category_code, match_item_codes, min_hours, max_hours, "
            "day_type, express_eligible, priority, display_text "
            "from delivery_sla_rules where active order by priority desc, code"
        )
        return [dict(r) for r in rows]
    return delivery.rules()


async def sync_status() -> dict:
    json_codes = {r["code"] for r in delivery.rules()}
    if not await _db_available():
        return {"db_available": False, "source": "json", "rules": len(json_codes), "in_sync": True}
    db_codes = {r["code"] for r in await list_rules()}
    missing = sorted(json_codes - db_codes)
    return {"db_available": True, "source": "supabase", "rules": len(db_codes),
            "in_sync": not missing, "missing": missing}


async def store_delivery_estimate(order_uuid: str, estimate: dict) -> dict | None:
    """Freeze the delivery estimate onto a confirmed order (idempotent — a
    re-confirm just rewrites the same snapshot)."""
    return await database.fetchrow(
        """
        update orders set
            delivery_mode = $2,
            turnaround_rule_codes = $3,
            turnaround_min_hours = $4,
            turnaround_max_hours = $5,
            turnaround_day_type = $6,
            turnaround_text = $7,
            estimated_delivery_start_at = $8,
            estimated_delivery_end_at = $9,
            estimated_delivery_text = $10,
            express_eligible = $11,
            express_applied = $12
        where id = $1
        returning *
        """,
        order_uuid,
        "EXPRESS" if estimate.get("applied_express") else "STANDARD",
        list(estimate.get("rule_codes") or []),
        estimate.get("min_hours"),
        estimate.get("max_hours"),
        estimate.get("day_type"),
        estimate.get("display_text"),
        estimate.get("estimated_delivery_start_at"),
        estimate.get("estimated_delivery_end_at"),
        estimate.get("estimated_delivery_text"),
        bool(estimate.get("express_eligible")),
        bool(estimate.get("applied_express")),
    )
