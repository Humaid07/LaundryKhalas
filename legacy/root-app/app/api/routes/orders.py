import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_admin
from app.db.session import get_db
from app.schemas.order import OrderEventRead, OrderRead
from app.services.orders import get_order, list_order_events, list_orders

router = APIRouter(prefix="/admin/orders", tags=["admin:orders"])


@router.get("", response_model=list[OrderRead], dependencies=[Depends(require_admin)])
async def list_orders_route(db: AsyncSession = Depends(get_db)):
    return await list_orders(db)


@router.get("/{order_id}", response_model=OrderRead, dependencies=[Depends(require_admin)])
async def get_order_route(order_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    order = await get_order(db, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.get(
    "/{order_id}/events", response_model=list[OrderEventRead], dependencies=[Depends(require_admin)]
)
async def list_order_events_route(order_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    order = await get_order(db, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return await list_order_events(db, order_id)
