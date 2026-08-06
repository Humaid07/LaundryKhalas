"""Immutable customer-quote snapshots + customer approvals (asyncpg / Supabase).

The snapshot is the frozen markup calculation (facility fee → customer price) tied
to (order, item, quote_version); the approval is the customer's decision on a
specific version. A new scope/price = a NEW version, so an old approval never
approves a new quote (spec §14/§15). Facility fee/markup never leave the snapshot
row onto a customer path.
"""
from __future__ import annotations

from db import database

_SNAP_COLS = (
    "id, quote_revision_id, order_id, order_item_id, quote_version, facility_fee, markup_type, "
    "markup_value, markup_rule_id, customer_subtotal, discount_percentage, discount_amount, "
    "delivery_charge, express_surcharge, final_customer_price, currency, pricing_rule_version, created_at"
)
_APP_COLS = (
    "id, order_id, order_item_id, quote_revision_id, quote_version, decision, final_price, "
    "scope, customer_message_id, decided_at"
)


def snapshot_to_read(row: dict | None, *, include_fee: bool = False) -> dict | None:
    """Customer-safe by default: the facility fee + markup are stripped unless an
    internal caller explicitly asks (include_fee=True)."""
    if not row:
        return None
    d = dict(row)
    d["id"] = str(d["id"])
    if not include_fee:
        for k in ("facility_fee", "markup_type", "markup_value", "markup_rule_id"):
            d.pop(k, None)
    return d


async def create_snapshot(
    *, quote_revision_id: str | None, order_id: str, order_item_id: str | None,
    quote_version: int, snapshot: dict, is_test_data: bool = False,
) -> dict | None:
    row = await database.fetchrow(
        f"""
        insert into customer_quote_snapshots
            (quote_revision_id, order_id, order_item_id, quote_version, facility_fee, markup_type,
             markup_value, markup_rule_id, customer_subtotal, discount_percentage, discount_amount,
             delivery_charge, express_surcharge, final_customer_price, currency, pricing_rule_version, is_test_data)
        values ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17)
        returning {_SNAP_COLS}
        """,
        quote_revision_id, order_id, order_item_id, quote_version,
        snapshot.get("facility_fee"), snapshot.get("markup_type"), snapshot.get("markup_value"),
        snapshot.get("markup_rule_id"), snapshot.get("customer_subtotal"),
        snapshot.get("discount_percentage"), snapshot.get("discount_amount"),
        snapshot.get("delivery_charge"), snapshot.get("express_surcharge"),
        snapshot.get("final_customer_price"), snapshot.get("currency", "AED"),
        snapshot.get("pricing_rule_version"), is_test_data,
    )
    return snapshot_to_read(row, include_fee=True)


async def record_approval(
    *, order_id: str, order_item_id: str | None, quote_revision_id: str | None,
    quote_version: int, decision: str, final_price=None, scope: str | None = None,
    customer_message_id: str | None = None, is_test_data: bool = False,
) -> dict | None:
    """Record a customer decision for a SPECIFIC quote version (idempotent per
    version+decision). Returns None on a duplicate."""
    row = await database.fetchrow(
        f"""
        insert into customer_quote_approvals
            (order_id, order_item_id, quote_revision_id, quote_version, decision, final_price,
             scope, customer_message_id, is_test_data)
        values ($1,$2,$3,$4,$5,$6,$7,$8,$9)
        on conflict (order_id, order_item_id, quote_version, decision) do nothing
        returning {_APP_COLS}
        """,
        order_id, order_item_id, quote_revision_id, quote_version, decision, final_price,
        scope, customer_message_id, is_test_data,
    )
    return dict(row) if row else None


async def latest_snapshot(order_id: str, order_item_id: str | None) -> dict | None:
    row = await database.fetchrow(
        f"select {_SNAP_COLS} from customer_quote_snapshots "
        "where order_id = $1 and coalesce(order_item_id,'') = coalesce($2,'') "
        "order by quote_version desc, created_at desc limit 1",
        order_id, order_item_id)
    return snapshot_to_read(row)  # customer-safe (no fee)
