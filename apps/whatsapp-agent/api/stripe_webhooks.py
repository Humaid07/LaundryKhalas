"""Stripe webhook endpoint — Invoicing settlement (spec §13, Phase 2b).

Stripe calls this when an invoice is paid/fails. The signature is ALWAYS verified
through the gateway (STRIPE_WEBHOOK_SECRET in live mode; the mock gateway just
parses the JSON envelope offline). We then map the event back to our order — by
``metadata.order_id`` first, else by the linked Stripe invoice id — and record the
settlement. The WhatsApp model never touches these fields; payment truth comes
only from a verified Stripe event.

Never auth-gated (like the other provider webhooks). Idempotent: a re-delivered
paid event is a no-op. An event we can't match is still acknowledged with 200 so
Stripe stops retrying (we never return 500 for an unmatched/ignored event).
"""
from __future__ import annotations

from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_db
from models import Order
from services import order_store
from services.payments import base as pay
from services.payments import get_gateway

router = APIRouter(prefix="/webhooks", tags=["stripe-webhook"])
logger = structlog.get_logger()

# Invoice lifecycle events we act on. Everything else is acknowledged and ignored.
_PAID_EVENTS = {"invoice.paid", "invoice.payment_succeeded"}
_FAILED_EVENTS = {"invoice.payment_failed"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _find_order(db: AsyncSession, data: dict) -> Order | None:
    """Map a Stripe invoice object back to our order: prefer the business
    order_id carried in metadata; fall back to the linked Stripe invoice id."""
    order_id = str((data.get("metadata") or {}).get("order_id") or "").strip()
    if order_id:
        order = await order_store.find_order_by_id(db, order_id)
        if order is not None:
            return order
    invoice_id = str(data.get("id") or "").strip()
    if invoice_id:
        result = await db.execute(select(Order).where(Order.stripe_invoice_id == invoice_id))
        return result.scalar_one_or_none()
    return None


@router.post("/stripe")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    raw_body = await request.body()
    signature = request.headers.get("stripe-signature")

    gateway = get_gateway()
    try:
        event = gateway.parse_webhook_event(raw_body, signature)
    except ValueError as exc:
        # Bad signature or unparseable payload → 400 (do NOT process).
        logger.warning("stripe_webhook_rejected", error=str(exc))
        raise HTTPException(status_code=400, detail="invalid webhook signature or payload")

    event_type = event.type
    if event_type not in _PAID_EVENTS and event_type not in _FAILED_EVENTS:
        logger.info("stripe_webhook_ignored", type=event_type, event_id=event.id)
        return {"received": True, "handled": False}

    data = event.data or {}
    order = await _find_order(db, data)
    if order is None:
        # Acknowledge so Stripe stops retrying; nothing to settle on our side.
        logger.warning("stripe_webhook_no_order", type=event_type, invoice=data.get("id"))
        return {"received": True, "handled": False}

    if event_type in _PAID_EVENTS:
        if order.payment_status == pay.PAID:
            return {"received": True, "handled": True, "idempotent": True}
        order.payment_status = pay.PAID
        order.paid_at = _now()
        order.amount_paid_minor = int(data.get("amount_paid") or data.get("amount_due") or 0)
        order.payment_currency = data.get("currency") or order.payment_currency
        if data.get("id"):
            order.stripe_invoice_id = data["id"]
        if data.get("hosted_invoice_url"):
            order.stripe_hosted_invoice_url = data["hosted_invoice_url"]
    else:  # _FAILED_EVENTS
        order.payment_status = pay.FAILED
        if data.get("id"):
            order.stripe_invoice_id = data["id"]

    await db.commit()
    logger.info(
        "stripe_webhook_settled",
        type=event_type,
        order=order.order_id,
        status=order.payment_status,
    )
    return {"received": True, "handled": True}
