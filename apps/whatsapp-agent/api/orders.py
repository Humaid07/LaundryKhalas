"""Read/write API over the mock order store. This is the surface a future
admin dashboard consumes to show active vs completed orders and ops metrics.
Everything is demo data (Order.is_demo) - no live operational system.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from schemas import OrderMetrics, OrderRead, OrderStatusUpdate
from services import order_store

router = APIRouter(prefix="/api/orders", tags=["orders"])


@router.get("/active", response_model=list[OrderRead])
async def active_orders(db: AsyncSession = Depends(get_db)):
    orders = await order_store.list_active_orders(db)
    return [order_store.to_dict(o) for o in orders]


@router.get("/completed", response_model=list[OrderRead])
async def completed_orders(db: AsyncSession = Depends(get_db)):
    orders = await order_store.list_completed_orders(db)
    return [order_store.to_dict(o) for o in orders]


@router.get("/metrics", response_model=OrderMetrics)
async def order_metrics(db: AsyncSession = Depends(get_db)):
    return await order_store.metrics(db)


@router.get("", response_model=list[OrderRead])
async def all_orders(status: str | None = None, db: AsyncSession = Depends(get_db)):
    orders = await order_store.list_orders(db, status=status)
    return [order_store.to_dict(o) for o in orders]


@router.get("/{order_id}", response_model=OrderRead)
async def get_one_order(order_id: str, db: AsyncSession = Depends(get_db)):
    order = await order_store.find_order_by_id(db, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found in demo data.")
    return order_store.to_dict(order)


@router.post("/{order_id}/complete", response_model=OrderRead)
async def complete_order(order_id: str, db: AsyncSession = Depends(get_db)):
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
    order = await order_store.find_order_by_id(db, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found in demo data.")
    try:
        await order_store.set_status(db, order, payload.status)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await db.commit()
    return order_store.to_dict(order)
