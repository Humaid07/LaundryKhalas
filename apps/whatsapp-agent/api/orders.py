"""Read/write API over the order store. This is the surface a future admin
dashboard consumes to show active vs completed orders and ops metrics.

Data source depends on DATABASE_MODE:
  * sqlite (default/local): the SQLAlchemy ``order_store`` (demo Order rows).
  * supabase (dev/test): the Supabase ``orders`` table via ``orders_repo``.
Both return the same OrderRead shape, so callers/tests are unaffected in local
mode (the supabase branch only triggers when DATABASE_MODE=supabase).
"""
from datetime import date

import structlog
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from channels.evolution_whatsapp import EvolutionWhatsAppChannel
from db import database, get_db
from db.repositories import conversations_repo, messages_repo, order_events_repo, orders_repo
from schemas import OrderMetrics, OrderPage, OrderRead, OrderStatusUpdate
from services import notifications, order_photos as photo_svc, order_store
from services.payments.invoicing import (
    build_invoice_request,
    ensure_invoice_for_order,
    render_payment_message,
)
from settings import get_settings

router = APIRouter(prefix="/api/orders", tags=["orders"])
logger = structlog.get_logger()

# Status for a drafted Stripe payment-link message held for operator approval.
_PENDING_PAYMENT_STATUS = "pending_approval"


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


@router.get("/{order_id}/photos")
async def order_photos_list(order_id: str):
    """Read-only ops view of an order's facility photos (intake + pre-dispatch),
    with per-stage counts. Ops/admin see any facility's order photos. Supabase-only.
    PII-safe metadata only; bytes come from the content endpoint below."""
    if not database.is_supabase_mode():
        return {"photos": [], "counts": {"intake": 0, "pre_dispatch": 0}}
    read = await orders_repo.get_read(order_id)
    if read is None:
        raise HTTPException(status_code=404, detail="Order not found.")
    all_photos = await photo_svc.list_photos(read["id"])
    counts = {"intake": 0, "pre_dispatch": 0}
    for p in all_photos:
        if p["stage"] in counts:
            counts[p["stage"]] += 1
    return {"photos": all_photos, "counts": counts}


@router.get("/{order_id}/photos/{photo_id}/content")
async def order_photo_content(order_id: str, photo_id: str):
    """Stream an order photo's bytes for the internal read-only gallery. Ops-guarded
    at the router level; the photo must belong to the order. Supabase-only."""
    if not database.is_supabase_mode():
        raise HTTPException(status_code=404, detail="Photo not found.")
    read = await orders_repo.get_read(order_id)
    if read is None:
        raise HTTPException(status_code=404, detail="Order not found.")
    result = await photo_svc.read_content_by_id(photo_id, order_uuid=read["id"])
    if result is None:
        raise HTTPException(status_code=404, detail="Photo not found.")
    data, content_type, file_name = result
    return Response(
        content=data,
        media_type=content_type,
        headers={
            "Cache-Control": "private, max-age=300",
            "Content-Disposition": f'inline; filename="{file_name}"',
        },
    )


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


# --- Stripe payment link (admin-triggered, spec §13) ------------------------
# Ops creates a Stripe invoice for a confirmed STRIPE order and queues the pay
# link as a message held for approval; a second call approves + sends it via the
# sanctioned human-send path. Supabase-mode only (mirrors the order-detail surface).
class PaymentLinkApprove(BaseModel):
    message_id: str
    operator_name: str | None = None


@router.post("/{order_id}/payment-link")
async def create_payment_link(order_id: str):
    """Create (once) a Stripe invoice for a confirmed STRIPE order and draft the
    pay-link message for approval. Idempotent: if a link already exists it is
    returned without creating a second invoice or a duplicate draft."""
    if not database.is_supabase_mode():
        raise HTTPException(status_code=400, detail="Payment links require the Supabase backend.")
    # Accept either the business order id (LK-AE-1024) or the internal uuid, so the
    # caller can pass whichever the order object carries (id::text avoids a uuid
    # parse error when a business id is supplied).
    row = await database.fetchrow(
        "select * from orders where order_id = $1 or id::text = $1", order_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Order not found.")
    order = dict(row)

    settings = get_settings()
    request, reason = build_invoice_request(
        order, automatic_tax=settings.stripe_automatic_tax_effective)
    already = bool(order.get("stripe_invoice_id"))
    if request is None and not already:
        # Genuinely ineligible (not confirmed / not STRIPE / no amount).
        raise HTTPException(status_code=409, detail=reason or "Order is not eligible for a payment link.")

    result = await ensure_invoice_for_order(order)  # None when already-invoiced (guard) or ineligible

    hosted = result.hosted_invoice_url if result else order.get("stripe_hosted_invoice_url")
    invoice_id = result.invoice_id if result else order.get("stripe_invoice_id")
    currency = (result.currency if result else order.get("payment_currency")) or order.get("currency") or "aed"
    if not hosted:
        raise HTTPException(status_code=502, detail="Could not obtain a payment link from the payment gateway.")

    # Draft the pending-approval message ONLY when a fresh invoice was just created
    # (avoids duplicate drafts on a re-click once the link exists).
    draft = None
    convo_id = order.get("conversation_id")
    if result is not None and convo_id:
        amount_major = (result.amount_due_minor or 0) / 100
        text = render_payment_message(
            name=str(order.get("customer_name") or ""), order_id=order_id,
            amount_major=amount_major, currency=currency, hosted_url=hosted)
        draft = await messages_repo.add_message(
            str(convo_id), "agent", text,
            status=_PENDING_PAYMENT_STATUS,
            metadata={"kind": "stripe_payment_link", "order_id": order_id, "invoice_id": invoice_id},
        )

    return {
        "order_id": order_id,
        "invoice_id": invoice_id,
        "hosted_invoice_url": hosted,
        "currency": currency,
        "already_existed": result is None,
        "draft_message": draft,
    }


@router.post("/{order_id}/payment-link/approve")
async def approve_payment_link(order_id: str, payload: PaymentLinkApprove):
    """Approve a drafted pay-link message and send it to the customer via the
    sanctioned human-send path (Evolution). Idempotent: a message that is no
    longer pending returns a no-op."""
    if not database.is_supabase_mode():
        raise HTTPException(status_code=400, detail="Payment links require the Supabase backend.")
    msg = await database.fetchrow(
        "select id, conversation_id, message_text, status from messages where id = $1",
        payload.message_id)
    if msg is None:
        raise HTTPException(status_code=404, detail="Draft message not found.")
    if msg["status"] != _PENDING_PAYMENT_STATUS:
        return {"status": "already_processed", "send_status": "skipped"}

    convo_id = str(msg["conversation_id"])
    text = msg["message_text"]
    # Human-approved send is the sanctioned way to send live WhatsApp in the MVP.
    await conversations_repo.start_human_takeover(convo_id, payload.operator_name)

    send_status = "stored"
    settings = get_settings()
    if settings.evolution_live_ready:
        phone = await conversations_repo.get_customer_phone(convo_id)
        if phone:
            try:
                sent = await EvolutionWhatsAppChannel.from_settings().send_text(
                    to_phone=phone, text=text)
                send_status = sent.status
            except Exception as exc:  # noqa: BLE001 - report, don't 500
                logger.warning("payment_link_send_failed", order=order_id, error=str(exc))
                send_status = "send_failed"

    new_status = "sent" if send_status in ("sent", "stored") else "send_failed"
    await messages_repo.set_status(payload.message_id, new_status)
    return {"status": new_status, "send_status": send_status}
