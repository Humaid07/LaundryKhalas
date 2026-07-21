import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import AGENT_ALLOWED_TRANSITIONS, Order, OrderEvent


class InvalidOrderTransition(Exception):
    pass


async def create_draft_order(
    db: AsyncSession,
    *,
    market_id: uuid.UUID,
    customer_id: uuid.UUID,
    service_type: str,
    items_json: dict,
    address_id: uuid.UUID | None,
    pickup_window_start: datetime | None,
    pickup_window_end: datetime | None,
    estimated_total: float | None,
    source_channel: str = "whatsapp",
) -> Order:
    order = Order(
        market_id=market_id,
        customer_id=customer_id,
        service_type=service_type,
        items_json=items_json,
        address_id=address_id,
        pickup_window_start=pickup_window_start,
        pickup_window_end=pickup_window_end,
        estimated_total=estimated_total,
        source_channel=source_channel,
        status="draft",
    )
    db.add(order)
    await db.flush()
    await _log_event(
        db, order=order, event_type="order_drafted", from_status=None, to_status="draft",
        actor_type="agent", actor_id="whatsapp_operations_agent",
    )
    return order


async def transition_order(
    db: AsyncSession,
    *,
    order: Order,
    to_status: str,
    actor_type: str,
    actor_id: str,
    metadata: dict | None = None,
) -> Order:
    from_status = order.status

    if actor_type == "agent" and (from_status, to_status) not in AGENT_ALLOWED_TRANSITIONS:
        raise InvalidOrderTransition(
            f"Agent may not transition order from {from_status!r} to {to_status!r}. "
            "Only draft -> created is agent-automatable in this MVP."
        )

    order.status = to_status
    await db.flush()
    await _log_event(
        db,
        order=order,
        event_type="status_change",
        from_status=from_status,
        to_status=to_status,
        actor_type=actor_type,
        actor_id=actor_id,
        metadata=metadata,
    )
    return order


async def assign_facility(
    db: AsyncSession, *, order: Order, facility_id: uuid.UUID, actor_type: str, actor_id: str
) -> Order:
    order.facility_id = facility_id
    await db.flush()
    await _log_event(
        db,
        order=order,
        event_type="facility_assigned",
        from_status=order.status,
        to_status=order.status,
        actor_type=actor_type,
        actor_id=actor_id,
        metadata={"facility_id": str(facility_id)},
    )
    return order


async def get_order(db: AsyncSession, order_id: uuid.UUID) -> Order | None:
    result = await db.execute(select(Order).where(Order.id == order_id))
    return result.scalar_one_or_none()


async def list_orders(db: AsyncSession, *, market_id: uuid.UUID | None = None) -> list[Order]:
    query = select(Order).order_by(Order.created_at.desc())
    if market_id:
        query = query.where(Order.market_id == market_id)
    result = await db.execute(query)
    return list(result.scalars().all())


async def list_order_events(db: AsyncSession, order_id: uuid.UUID) -> list[OrderEvent]:
    result = await db.execute(
        select(OrderEvent).where(OrderEvent.order_id == order_id).order_by(OrderEvent.created_at)
    )
    return list(result.scalars().all())


async def _log_event(
    db: AsyncSession,
    *,
    order: Order,
    event_type: str,
    from_status: str | None,
    to_status: str | None,
    actor_type: str,
    actor_id: str,
    metadata: dict | None = None,
) -> OrderEvent:
    event = OrderEvent(
        order_id=order.id,
        event_type=event_type,
        from_status=from_status,
        to_status=to_status,
        actor_type=actor_type,
        actor_id=actor_id,
        metadata_json=metadata or {},
    )
    db.add(event)
    await db.flush()
    return event
