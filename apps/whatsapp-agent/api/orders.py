"""Read/write API over the order store. This is the surface a future admin
dashboard consumes to show active vs completed orders and ops metrics.

Data source depends on DATABASE_MODE:
  * sqlite (default/local): the SQLAlchemy ``order_store`` (demo Order rows).
  * supabase (dev/test): the Supabase ``orders`` table via ``orders_repo``.
Both return the same OrderRead shape, so callers/tests are unaffected in local
mode (the supabase branch only triggers when DATABASE_MODE=supabase).
"""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from db import database, get_db
from db.repositories import conversations_repo, order_events_repo, orders_repo
from schemas import OrderMetrics, OrderPage, OrderRead, OrderStatusUpdate
from services import notifications, order_store

router = APIRouter(prefix="/api/orders", tags=["orders"])


@router.get("/search", response_model=OrderPage)
async def search_orders(
    search: str | None = None,
    status: str | None = None,
    service_id: str | None = None,
    pickup_date: date | None = None,
    source: str | None = None,
    needs_attention: bool | None = None,
    sort: str = "attention",
    page: int = 1,
    page_size: int = 25,
):
    """Filtered/sorted/paginated orders for the dashboard Orders section. Demo
    rows are excluded unless ENABLE_DEMO_DATA=true. Supabase-only (the Orders
    section is a live-data feature); returns an empty page in local SQLite mode."""
    if not database.is_supabase_mode():
        return {"orders": [], "total": 0, "page": page, "page_size": page_size}
    orders, total = await orders_repo.list_for_dashboard(
        search=search, status=status, service_id=service_id, pickup_date=pickup_date,
        source=source, needs_attention=needs_attention, sort=sort,
        page=page, page_size=page_size,
    )
    return {"orders": orders, "total": total, "page": page, "page_size": page_size}


@router.get("/active", response_model=list[OrderRead])
async def active_orders(db: AsyncSession = Depends(get_db)):
    if database.is_supabase_mode():
        return await orders_repo.list_active_read()
    orders = await order_store.list_active_orders(db)
    return [order_store.to_dict(o) for o in orders]


@router.get("/completed", response_model=list[OrderRead])
async def completed_orders(db: AsyncSession = Depends(get_db)):
    if database.is_supabase_mode():
        return await orders_repo.list_completed_read()
    orders = await order_store.list_completed_orders(db)
    return [order_store.to_dict(o) for o in orders]


@router.get("/metrics", response_model=OrderMetrics)
async def order_metrics(db: AsyncSession = Depends(get_db)):
    if database.is_supabase_mode():
        return await orders_repo.metrics()
    return await order_store.metrics(db)


@router.get("/metrics/summary")
async def order_metrics_summary():
    """Real Orders-section metric cards (new today, active, confirmed pickups,
    completed, cancelled, needs attention). Supabase-only; zeros in SQLite mode."""
    if not database.is_supabase_mode():
        return {"new_today": 0, "active_orders": 0, "confirmed_pickups": 0,
                "completed": 0, "cancelled": 0, "needs_attention": 0}
    return await orders_repo.dashboard_metrics()


@router.get("", response_model=list[OrderRead])
async def all_orders(status: str | None = None, db: AsyncSession = Depends(get_db)):
    if database.is_supabase_mode():
        return await orders_repo.list_read(status=status)
    orders = await order_store.list_orders(db, status=status)
    return [order_store.to_dict(o) for o in orders]


@router.get("/{order_id}", response_model=OrderRead)
async def get_one_order(order_id: str, db: AsyncSession = Depends(get_db)):
    if database.is_supabase_mode():
        read = await orders_repo.get_read(order_id)
        if read is None:
            raise HTTPException(status_code=404, detail="Order not found in demo data.")
        return read
    order = await order_store.find_order_by_id(db, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found in demo data.")
    return order_store.to_dict(order)


@router.get("/{order_id}/events")
async def order_events(order_id: str):
    """Audit trail for an order (order_events, oldest first). Supabase-only."""
    if not database.is_supabase_mode():
        return []
    read = await orders_repo.get_read(order_id)
    if read is None:
        raise HTTPException(status_code=404, detail="Order not found.")
    return await order_events_repo.list_for_order(read["id"])


@router.get("/{order_id}/conversation")
async def order_conversation(order_id: str):
    """The WhatsApp conversation linked to an order (by stored conversation_id,
    never by phone/name matching). Supabase-only."""
    if not database.is_supabase_mode():
        raise HTTPException(status_code=404, detail="Conversation requires Supabase mode.")
    read = await orders_repo.get_read(order_id)
    if read is None:
        raise HTTPException(status_code=404, detail="Order not found.")
    if not read.get("conversation_id"):
        raise HTTPException(status_code=404, detail="Order has no linked conversation.")
    convo = await conversations_repo.get_conversation(read["conversation_id"])
    if convo is None:
        raise HTTPException(status_code=404, detail="Linked conversation not found.")
    return convo


@router.patch("/{order_id}/status", response_model=OrderRead)
async def patch_order_status(
    order_id: str, payload: OrderStatusUpdate, db: AsyncSession = Depends(get_db)
):
    """Dashboard status update (PATCH). Validated + persisted + writes an
    order_events audit record. Same effect as POST /{order_id}/status."""
    return await update_order_status(order_id, payload, db)


@router.post("/{order_id}/complete", response_model=OrderRead)
async def complete_order(order_id: str, db: AsyncSession = Depends(get_db)):
    if database.is_supabase_mode():
        read = await orders_repo.complete(order_id)
        if read is None:
            raise HTTPException(status_code=404, detail="Order not found in demo data.")
        return read
    order = await order_store.find_order_by_id(db, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found in demo data.")
    await order_store.mark_completed(db, order)
    await db.commit()
    return order_store.to_dict(order)


@router.post("/{order_id}/status", response_model=OrderRead)
async def update_order_status(
    order_id: str, payload: OrderStatusUpdate, db: AsyncSession = Depends(get_db)
):
    if database.is_supabase_mode():
        try:
            read = await orders_repo.set_status(
                order_id, payload.status, actor_name=payload.actor_name)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if read is None:
            raise HTTPException(status_code=404, detail="Order not found in demo data.")
        # After-commit customer notification (idempotent; never rolls back).
        await notifications.notify_status_change(read, payload.status)
        return read
    order = await order_store.find_order_by_id(db, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found in demo data.")
    try:
        await order_store.set_status(db, order, payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await db.commit()
    return order_store.to_dict(order)
