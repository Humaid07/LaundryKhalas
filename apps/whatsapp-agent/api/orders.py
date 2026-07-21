"""Read/write API over the order store. This is the surface a future admin
dashboard consumes to show active vs completed orders and ops metrics.

Data source depends on DATABASE_MODE:
  * sqlite (default/local): the SQLAlchemy ``order_store`` (demo Order rows).
  * supabase (dev/test): the Supabase ``orders`` table via ``orders_repo``.
Both return the same OrderRead shape, so callers/tests are unaffected in local
mode (the supabase branch only triggers when DATABASE_MODE=supabase).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from db import database, get_db
from db.repositories import orders_repo
from schemas import OrderMetrics, OrderRead, OrderStatusUpdate
from services import order_store

router = APIRouter(prefix="/api/orders", tags=["orders"])


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
            read = await orders_repo.set_status(order_id, payload.status)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if read is None:
            raise HTTPException(status_code=404, detail="Order not found in demo data.")
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
