"""Order reads/writes against the dev/test Supabase schema.

Rows are mapped to the existing ``OrderRead`` shape so the same FastAPI order
endpoints serve either SQLite (local) or Supabase (dev/test) data unchanged.
"""
from __future__ import annotations

import re

from db import database
from db.repositories import conversations_repo, order_events_repo
from services import order_store  # reuse status_label + active-status logic

_TERMINAL = {order_store.COMPLETED, order_store.CANCELLED}
_HIDDEN_FROM_ACTIVE = _TERMINAL | {order_store.DRAFT}

_SELECT = "select * from orders"


def _item_label(item) -> str:
    """Human label for a stored item — dicts ({item, quantity}) render as
    '2x Suit'; plain strings pass through."""
    if isinstance(item, dict):
        name = item.get("item") or item.get("name") or "Item"
        qty = item.get("quantity")
        return f"{qty}x {name}" if qty else str(name)
    return str(item)


def to_read(row: dict, *, include_address: bool = False) -> dict:
    """Map a Supabase orders row to the OrderRead schema shape.

    ``include_address`` is False for broad list responses (privacy: the full
    pickup address is never returned in a list) and True only for the secure
    single-order detail endpoint (CLAUDE.md §7)."""
    status = row.get("status") or "active"
    items = row.get("items") or []
    if isinstance(items, str):
        items = [items]
    return {
        "id": str(row["id"]),
        "order_id": row["order_id"],
        "conversation_id": str(row["conversation_id"]) if row.get("conversation_id") else None,
        "customer_name": row.get("customer_name"),
        "service_type": row.get("service"),
        "items": [_item_label(i) for i in items],
        "pickup_area": row.get("area"),
        "pickup_address": row.get("pickup_address") if include_address else None,
        "pickup_date": row.get("pickup_slot"),
        "pickup_time": None,
        "city": row.get("city"),
        "delivery_preference": row.get("delivery_slot"),
        "status": status,
        "status_label": order_store.status_label(status),
        "notes": row.get("notes"),
        "change_request": row.get("change_request"),
        "amount": float(row["amount"]) if row.get("amount") is not None else None,
        "currency": "AED",
        "facility": row.get("facility"),
        "driver": row.get("driver"),
        "payment": row.get("payment_status"),
        "source_channel": row.get("source_channel") or "whatsapp",
        "is_demo": bool(row.get("is_demo")),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "completed_at": row.get("completed_at"),
    }


async def list_active_read() -> list[dict]:
    rows = await database.fetch(
        _SELECT + " where status <> all($1::text[]) order by updated_at desc",
        list(_HIDDEN_FROM_ACTIVE),
    )
    return [to_read(r) for r in rows]


async def list_completed_read() -> list[dict]:
    rows = await database.fetch(
        _SELECT + " where status = $1 order by completed_at desc nulls last",
        order_store.COMPLETED,
    )
    return [to_read(r) for r in rows]


async def list_read(status: str | None = None) -> list[dict]:
    if status:
        rows = await database.fetch(_SELECT + " where status = $1 order by updated_at desc", status)
    else:
        rows = await database.fetch(_SELECT + " order by updated_at desc")
    return [to_read(r) for r in rows]


async def get_read(order_id: str) -> dict | None:
    row = await database.fetchrow(
        _SELECT + " where upper(replace(order_id,' ','')) = upper(replace($1,' ','')) ",
        order_id,
    )
    # Secure single-order detail: the full pickup address IS included here (and
    # only here) — list responses never expose it.
    return to_read(row, include_address=True) if row else None


async def complete(order_id: str) -> dict | None:
    row = await database.fetchrow(
        "update orders set status = 'completed', completed_at = now() "
        "where upper(replace(order_id,' ','')) = upper(replace($1,' ','')) returning *",
        order_id,
    )
    return to_read(row) if row else None


async def set_status(order_id: str, status: str) -> dict | None:
    if status not in order_store.ORDER_STATUSES:
        raise ValueError(f"Unknown status: {status}")
    completed_at = ", completed_at = now()" if status == order_store.COMPLETED else ""
    row = await database.fetchrow(
        f"update orders set status = $2{completed_at} "
        "where upper(replace(order_id,' ','')) = upper(replace($1,' ','')) returning *",
        order_id,
        status,
    )
    return to_read(row) if row else None


# --------------------------------------------------------------------------
# WhatsApp order capture — draft create/update from a live conversation
# --------------------------------------------------------------------------
# Test-mode business ids for WhatsApp-captured orders. Kept distinct from the
# seeded demo ids (LK-AE-102x) so they are obviously the live-capture orders.
_TEST_ORDER_PREFIX = "LC-TEST-"
_TEST_ORDER_BASE = 1000

# orders column -> order_events event_type, emitted the first time a field is set.
_FIELD_EVENTS = {
    "service": "service_selected",
    "items": "items_added",
    "pickup_address": "address_added",
    "pickup_slot": "pickup_slot_added",
    "payment_method": "payment_method_added",
}


async def next_test_order_id() -> str:
    rows = await database.fetch(
        "select order_id from orders where order_id like $1", _TEST_ORDER_PREFIX + "%"
    )
    highest = _TEST_ORDER_BASE
    for r in rows:
        m = re.search(r"(\d+)\s*$", r.get("order_id") or "")
        if m:
            highest = max(highest, int(m.group(1)))
    return f"{_TEST_ORDER_PREFIX}{highest + 1}"


async def get_open_for_conversation(conversation_id: str) -> dict | None:
    """Most recent non-terminal order linked to a conversation (draft or active)."""
    return await database.fetchrow(
        _SELECT + " where conversation_id = $1 and status <> all($2::text[]) "
        "order by created_at desc limit 1",
        conversation_id,
        list(_TERMINAL),
    )


def _estimate_amount(details) -> float | None:
    """Best-effort estimate ONLY for per-item services with known quantities
    (e.g. Dry Cleaning 15 AED/item). Never invents a price for per-kg or
    unpriced services — those stay null (RULE 8)."""
    from agents.whatsapp_agent import tools

    if not details.service_key or not details.items:
        return None
    price = tools.lookup_price(details.service_key)
    if not price or price.get("unit") != "item":
        return None
    total_qty = sum(int(i.get("quantity", 1) or 1) for i in details.items)
    amount = total_qty * float(price["price"])
    if price.get("min_price"):
        amount = max(amount, float(price["min_price"]))
    return round(amount, 2)


def _confirmed_status(details) -> str:
    """Status a confirmed booking lands in: pickup_scheduled when a pickup slot
    is known, otherwise active."""
    return order_store.PICKUP_SCHEDULED if details.pickup_slot else order_store.ACTIVE


async def create_or_update_draft_from_conversation(
    *, conversation_id: str, customer: dict | None, details
) -> dict:
    """Create (or update-in-place) the draft order for a conversation from the
    accumulated ``OrderDetails`` and write the matching order_events.

    Returns ``{"row": <orders row>, "created": bool, "confirmed_now": bool}``.
    The order stays ``draft`` until the customer confirms AND enough detail
    exists (service/items + a pickup area/address); only then is it promoted to
    pickup_scheduled/active. Never creates duplicates — an open order for the
    conversation is updated instead. ``linked_order_id`` is set on the
    conversation so the inbox/dashboard can cross-reference.
    """
    existing = await get_open_for_conversation(conversation_id)
    amount = _estimate_amount(details)
    confirmable = details.confirmed and details.is_confirmable()

    target = {
        "customer_name": details.name or (customer or {}).get("display_name"),
        "service": details.service_label,
        "items": details.items or None,
        "city": details.city,
        "area": details.area,
        "pickup_address": details.address,
        "pickup_slot": details.pickup_slot,
        "delivery_slot": details.delivery_slot,
        "payment_method": details.payment_method,
        "amount": amount,
    }

    if existing is None:
        status = _confirmed_status(details) if confirmable else order_store.DRAFT
        order_id = await next_test_order_id()
        row = await database.fetchrow(
            """
            insert into orders
                (order_id, conversation_id, customer_id, customer_name, service,
                 items, city, area, pickup_address, pickup_slot, delivery_slot,
                 payment_method, amount, status, source_channel, notes,
                 is_test_data, is_demo, environment, test_scenario_id, created_by_seed)
            values ($1, $2, $3, $4, $5, $6::jsonb, $7, $8, $9, $10, $11, $12, $13,
                    $14, 'whatsapp', $15, true, false, 'dev', 'whatsapp_live_capture', false)
            returning *
            """,
            order_id,
            conversation_id,
            (customer or {}).get("id"),
            target["customer_name"],
            target["service"],
            target["items"] or [],
            target["city"],
            target["area"],
            target["pickup_address"],
            target["pickup_slot"],
            target["delivery_slot"],
            target["payment_method"],
            target["amount"],
            status,
            "Created from WhatsApp conversation.",
        )
        await conversations_repo.link_order(conversation_id, order_id)
        await order_events_repo.create(
            order_uuid=row["id"], event_type="order_created", to_status=status,
            notes=f"Draft order {order_id} created from WhatsApp.",
        )
        for col, event_type in _FIELD_EVENTS.items():
            if target.get(col):
                await order_events_repo.create(
                    order_uuid=row["id"], event_type=event_type,
                    notes=f"{col} captured.",
                )
        if confirmable:
            await order_events_repo.create(
                order_uuid=row["id"], event_type="order_confirmed", to_status=status,
                notes="Customer confirmed the booking.",
            )
        return {"row": row, "created": True, "confirmed_now": confirmable}

    # --- update in place: only set fields that are newly known -----------------
    changed_cols: list[str] = []
    sets: list[str] = []
    values: list = []
    for col, new_val in target.items():
        if new_val and existing.get(col) != new_val:
            values.append(new_val)
            cast = "::jsonb" if col == "items" else ""
            sets.append(f"{col} = ${len(values)}{cast}")
            changed_cols.append(col)

    confirmed_now = (
        confirmable and existing.get("status") == order_store.DRAFT
    )
    new_status = _confirmed_status(details) if confirmed_now else None
    if new_status:
        values.append(new_status)
        sets.append(f"status = ${len(values)}")

    row = existing
    if sets:
        values.append(existing["id"])
        row = await database.fetchrow(
            f"update orders set {', '.join(sets)} where id = ${len(values)} returning *",
            *values,
        )

    for col in changed_cols:
        event_type = _FIELD_EVENTS.get(col)
        if event_type and not existing.get(col):  # newly-added field
            await order_events_repo.create(
                order_uuid=existing["id"], event_type=event_type, notes=f"{col} captured.",
            )
    if confirmed_now:
        await order_events_repo.create(
            order_uuid=existing["id"], event_type="order_confirmed",
            from_status=order_store.DRAFT, to_status=new_status,
            notes="Customer confirmed the booking.",
        )
        await order_events_repo.create(
            order_uuid=existing["id"], event_type="order_status_changed",
            from_status=order_store.DRAFT, to_status=new_status,
        )

    return {"row": row, "created": False, "confirmed_now": confirmed_now}


async def metrics() -> dict:
    rows = await database.fetch("select status from orders")
    by_status: dict[str, int] = {}
    for r in rows:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
    return {
        "active_orders": sum(v for k, v in by_status.items() if k not in _HIDDEN_FROM_ACTIVE),
        "completed_orders": by_status.get(order_store.COMPLETED, 0),
        "cancellation_requests": by_status.get(order_store.CANCELLATION_REQUESTED, 0),
        "pickup_change_requests": by_status.get(order_store.PICKUP_CHANGE_REQUESTED, 0),
        "support_required": by_status.get(order_store.SUPPORT_REQUIRED, 0),
        "total_orders": len(rows),
        "orders_by_status": by_status,
    }
