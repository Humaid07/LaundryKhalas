"""Order state store for the standalone WhatsApp Agent.

This is the layer that makes the chat *stateful*: the conversation doesn't
just produce replies, it creates and mutates a real, queryable Order row
behind the scenes (draft -> active -> ... -> completed/cancelled). A future
dashboard reads from exactly these functions.

Persistence is the existing async SQLAlchemy/SQLite database (the same one
that already holds conversations/messages), so orders survive a restart.
Every function takes the request's `AsyncSession` and mutates in place;
callers commit. All data is demo/mock - see is_demo.

The interface here is deliberately storage-agnostic in shape
(create/update/get/find/list/mark_completed/...); swapping SQLite for
Postgres later needs no change to callers.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Order

# ---------------------------------------------------------------------------
# Status model
# ---------------------------------------------------------------------------
DRAFT = "draft"
ACTIVE = "active"
PICKUP_SCHEDULED = "pickup_scheduled"
PICKED_UP = "picked_up"
IN_CLEANING = "in_cleaning"
READY_FOR_DELIVERY = "ready_for_delivery"
OUT_FOR_DELIVERY = "out_for_delivery"
COMPLETED = "completed"
CANCELLED = "cancelled"
SUPPORT_REQUIRED = "support_required"
CANCELLATION_REQUESTED = "cancellation_requested"
PICKUP_CHANGE_REQUESTED = "pickup_change_requested"
ABANDONED = "abandoned"  # a draft that expired without confirmation (spec §29)

ORDER_STATUSES = [
    DRAFT,
    ACTIVE,
    PICKUP_SCHEDULED,
    PICKED_UP,
    IN_CLEANING,
    READY_FOR_DELIVERY,
    OUT_FOR_DELIVERY,
    COMPLETED,
    CANCELLED,
    ABANDONED,
    SUPPORT_REQUIRED,
    CANCELLATION_REQUESTED,
    PICKUP_CHANGE_REQUESTED,
]

# "Active" for the dashboard = anything in flight: not a bare draft, and not
# a terminal completed/cancelled order. Cancellation/pickup-change requests
# stay visible as active because the team still has to action them.
_TERMINAL = {COMPLETED, CANCELLED, ABANDONED}
_HIDDEN_FROM_ACTIVE = _TERMINAL | {DRAFT}

# Human-readable label for chat replies (only where the raw status isn't
# already readable). Missing keys fall back to status.replace("_", " ").
STATUS_LABELS = {
    PICKUP_SCHEDULED: "pickup scheduled",
    PICKED_UP: "picked up",
    IN_CLEANING: "in cleaning",
    READY_FOR_DELIVERY: "ready for delivery",
    OUT_FOR_DELIVERY: "out for delivery",
    SUPPORT_REQUIRED: "with our support team",
    CANCELLATION_REQUESTED: "pending cancellation review",
    PICKUP_CHANGE_REQUESTED: "pending a pickup-time change",
}


def status_label(status: str) -> str:
    return STATUS_LABELS.get(status, status.replace("_", " "))


def is_active_status(status: str) -> bool:
    return status not in _HIDDEN_FROM_ACTIVE


# ---------------------------------------------------------------------------
# Demo/seed orders (idempotent) - the four IDs the test script uses.
# ---------------------------------------------------------------------------
_DEMO_ORDERS = [
    {
        "order_id": "LK-AE-1024",
        "customer_name": "Amaan",
        "service_type": "Wash & Fold + Dry Cleaning",
        "items": ["Mixed laundry", "2 shirts for dry cleaning"],
        "status": PICKUP_SCHEDULED,
        "pickup_date": "Today",
        "pickup_time": "6 PM – 8 PM",
        "pickup_area": "Dubai Marina",
        "city": "Dubai",
        "facility": "Dubai Marina Facility",
        "driver": "Ahmed Khan",
        "payment": "Pay on delivery",
        "amount": 145.0,
    },
    {
        "order_id": "LK-AE-1025",
        "customer_name": "Sarah",
        "service_type": "Duvet Cleaning",
        "items": ["1 duvet"],
        "status": IN_CLEANING,
        "pickup_date": "Completed",
        "pickup_area": "Abu Dhabi",
        "city": "Abu Dhabi",
        "facility": "Abu Dhabi Facility",
        "driver": "Fatima Noor",
        "payment": "Pending",
        "amount": 90.0,
    },
    {
        "order_id": "LK-AE-1026",
        "customer_name": "Jumeirah Hotel",
        "service_type": "Business Laundry",
        "items": ["Bulk business laundry"],
        "status": READY_FOR_DELIVERY,
        "pickup_area": "Dubai",
        "city": "Dubai",
        "facility": "Business Bay Facility",
        "payment": "Invoice",
        "amount": 2800.0,
    },
    {
        "order_id": "LK-AE-1027",
        "customer_name": "Test User",
        "service_type": "Ironing / Pressing",
        "items": ["Assorted ironing"],
        "status": COMPLETED,
        "pickup_area": "Sharjah",
        "city": "Sharjah",
        "payment": "Paid",
        "amount": 60.0,
    },
]


async def seed_demo_orders(db: AsyncSession) -> None:
    """Insert the demo orders if they aren't there yet. Safe to call on
    every startup - matches by order_id, never duplicates."""
    for data in _DEMO_ORDERS:
        result = await db.execute(select(Order).where(Order.order_id == data["order_id"]))
        if result.scalar_one_or_none() is not None:
            continue
        order = Order(source_channel="whatsapp", is_demo=True, **data)
        if order.status == COMPLETED:
            order.completed_at = datetime.now(timezone.utc)
        db.add(order)
    await db.commit()


# ---------------------------------------------------------------------------
# ID generation
# ---------------------------------------------------------------------------
_NEW_ORDER_BASE = 2031  # demo seed uses 1024-1027; new bookings start here


async def next_order_id(db: AsyncSession, *, market_code: str = "AE") -> str:
    """LK-<MARKET>-<n>, n continuing after the highest existing numeric
    suffix (>= 2031 so it never collides with the 10xx demo seeds)."""
    result = await db.execute(select(Order.order_id))
    highest = _NEW_ORDER_BASE - 1
    for (oid,) in result.all():
        m = re.search(r"(\d+)\s*$", oid or "")
        if m:
            highest = max(highest, int(m.group(1)))
    return f"LK-{market_code}-{highest + 1}"


# ---------------------------------------------------------------------------
# CRUD / lookups
# ---------------------------------------------------------------------------
async def create_order(db: AsyncSession, **fields) -> Order:
    order = Order(**fields)
    db.add(order)
    await db.flush()
    return order


async def update_order(db: AsyncSession, order: Order, **fields) -> Order:
    for key, value in fields.items():
        setattr(order, key, value)
    await db.flush()
    return order


async def get_order(db: AsyncSession, internal_id: str) -> Order | None:
    result = await db.execute(select(Order).where(Order.id == internal_id))
    return result.scalar_one_or_none()


def _normalize(raw: str) -> str:
    return re.sub(r"\s+", "", (raw or "").strip().upper())


async def find_order_by_id(db: AsyncSession, order_id_text: str) -> Order | None:
    """Look up by the human/business order id. Case/space insensitive, and
    tolerant of a customer typing just the trailing number (e.g. "1024"
    finds "LK-AE-1024"). Never invents an order - returns None if unknown."""
    if not order_id_text:
        return None
    wanted = _normalize(order_id_text)
    result = await db.execute(select(Order))
    orders = list(result.scalars().all())

    for order in orders:
        if _normalize(order.order_id) == wanted:
            return order

    if wanted.isdigit():  # bare number -> match trailing digits of an id
        for order in orders:
            if _normalize(order.order_id).endswith(wanted):
                return order
    return None


async def get_draft_for_conversation(db: AsyncSession, conversation_id: str) -> Order | None:
    result = await db.execute(
        select(Order)
        .where(Order.conversation_id == conversation_id, Order.status == DRAFT)
        .order_by(Order.created_at.desc())
    )
    return result.scalars().first()


async def latest_order_for_conversation(db: AsyncSession, conversation_id: str) -> Order | None:
    """Most recent non-terminal order linked to a conversation (draft or
    active) - used to attach 'add more items' when no id was given."""
    result = await db.execute(
        select(Order)
        .where(Order.conversation_id == conversation_id)
        .where(Order.status.not_in(list(_TERMINAL)))
        .order_by(Order.updated_at.desc())
    )
    return result.scalars().first()


async def list_active_orders(db: AsyncSession) -> list[Order]:
    result = await db.execute(
        select(Order).where(Order.status.not_in(list(_HIDDEN_FROM_ACTIVE)))
        .order_by(Order.updated_at.desc())
    )
    return list(result.scalars().all())


async def list_completed_orders(db: AsyncSession) -> list[Order]:
    result = await db.execute(
        select(Order).where(Order.status == COMPLETED).order_by(Order.completed_at.desc())
    )
    return list(result.scalars().all())


async def list_orders(db: AsyncSession, *, status: str | None = None) -> list[Order]:
    stmt = select(Order).order_by(Order.updated_at.desc())
    if status:
        stmt = stmt.where(Order.status == status)
    result = await db.execute(stmt)
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Mutations driven by the conversation / dashboard
# ---------------------------------------------------------------------------
async def mark_completed(db: AsyncSession, order: Order) -> Order:
    order.status = COMPLETED
    order.completed_at = datetime.now(timezone.utc)
    await db.flush()
    return order


async def set_status(db: AsyncSession, order: Order, status: str) -> Order:
    if status not in ORDER_STATUSES:
        raise ValueError(f"Unknown status: {status}")
    order.status = status
    if status == COMPLETED:
        order.completed_at = datetime.now(timezone.utc)
    await db.flush()
    return order


async def add_order_note(db: AsyncSession, order: Order, note: str) -> Order:
    note = (note or "").strip()
    if note:
        order.notes = f"{order.notes}\n{note}" if order.notes else note
    await db.flush()
    return order


async def add_order_items(db: AsyncSession, order: Order, items: str | list[str]) -> Order:
    new_items = [items] if isinstance(items, str) else list(items)
    new_items = [i.strip() for i in new_items if i and i.strip()]
    order.items = (order.items or []) + new_items
    await db.flush()
    return order


async def request_cancellation(db: AsyncSession, order: Order) -> Order:
    """Never actually cancels - records that the customer asked, for the
    team to review. Leaves a completed order untouched."""
    if order.status == COMPLETED:
        return order
    order.status = CANCELLATION_REQUESTED
    await add_order_note(db, order, "Customer requested cancellation via WhatsApp (demo).")
    await db.flush()
    return order


async def request_pickup_change(db: AsyncSession, order: Order, new_time: str) -> Order:
    order.status = PICKUP_CHANGE_REQUESTED
    order.change_request = f"Requested new pickup time: {new_time}".strip()
    await add_order_note(db, order, f"Pickup-time change requested (demo): {new_time}.")
    await db.flush()
    return order


# ---------------------------------------------------------------------------
# Serialization + metrics for API / dashboard
# ---------------------------------------------------------------------------
def to_dict(order: Order) -> dict:
    return {
        "id": order.id,
        "order_id": order.order_id,
        "conversation_id": order.conversation_id,
        "customer_name": order.customer_name,
        "service_type": order.service_type,
        "items": order.items or [],
        "pickup_area": order.pickup_area,
        "pickup_address": order.pickup_address,
        "pickup_date": order.pickup_date,
        "pickup_time": order.pickup_time,
        "city": order.city,
        "delivery_preference": order.delivery_preference,
        "status": order.status,
        "status_label": status_label(order.status),
        "notes": order.notes,
        "change_request": order.change_request,
        "amount": order.amount,
        "currency": order.currency,
        "facility": order.facility,
        "driver": order.driver,
        "payment": order.payment,
        "source_channel": order.source_channel,
        "is_demo": order.is_demo,
        "created_at": order.created_at,
        "updated_at": order.updated_at,
        "completed_at": order.completed_at,
    }


async def metrics(db: AsyncSession) -> dict:
    orders = await list_orders(db)
    by_status: dict[str, int] = {}
    for order in orders:
        by_status[order.status] = by_status.get(order.status, 0) + 1
    return {
        "active_orders": sum(1 for o in orders if is_active_status(o.status)),
        "completed_orders": by_status.get(COMPLETED, 0),
        "cancellation_requests": by_status.get(CANCELLATION_REQUESTED, 0),
        "pickup_change_requests": by_status.get(PICKUP_CHANGE_REQUESTED, 0),
        "support_required": by_status.get(SUPPORT_REQUIRED, 0),
        "total_orders": len(orders),
        "orders_by_status": by_status,
    }
