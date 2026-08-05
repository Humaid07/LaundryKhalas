"""Website "Order Now" intent capture (spec §24).

Public endpoint the marketing site calls when a visitor clicks Order Now. It ALWAYS
records the intent (analytics) and schedules abandonment follow-ups ONLY for an
identified, consented visitor with a verified WhatsApp number — never fingerprinting a
number, never treating an unsent prefilled message as an inbound conversation. The
decision is made by services/web_order_intent; scheduling goes through the centralized
follow-up scheduler (Supabase-only queue).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

import structlog

from db import database, get_db
from models import WebOrderIntent
from services import followup_scheduler, persona_assignment
from services import web_order_intent as woi
from services.clock import now as clock_now

logger = structlog.get_logger()
router = APIRouter(tags=["web"])


class WebOrderIntentRequest(BaseModel):
    session_id: str
    source_page: str | None = None
    service_code: str | None = None
    market: str = "AE"
    campaign: dict | None = None
    whatsapp_number: str | None = None
    consent: bool = False
    customer_id: str | None = None


async def _schedule_web_abandonment(session_id: str, number: str, market: str) -> None:
    """Queue the three §24 abandonment follow-ups for a consented visitor. Supabase-only
    (the queue lives there); idempotent via dedupe_key; never raises."""
    try:
        if not database.is_supabase_mode():
            return
        from db.repositories import scheduled_followups_repo
        persona = persona_assignment.select_for_key(number)
        rows = followup_scheduler.web_abandonment_rows(
            session_id, clock_now(market), market=market, persona=persona,
            customer_phone=number)
        await scheduled_followups_repo.schedule(rows)
    except Exception as exc:  # noqa: BLE001 - capture must never fail on scheduling
        logger.warning("web_abandonment_schedule_failed", error=str(exc))


@router.post("/api/web/order-intent")
async def capture_order_intent(payload: WebOrderIntentRequest, db: AsyncSession = Depends(get_db)):
    """Record an Order-Now click and, only if allowed, arm abandonment outreach."""
    intent = woi.WebOrderIntentInput(
        session_id=payload.session_id, source_page=payload.source_page,
        service_code=payload.service_code, market=(payload.market or "AE"),
        campaign=payload.campaign or {}, whatsapp_number=payload.whatsapp_number,
        consent=payload.consent, customer_id=payload.customer_id)
    decision = woi.evaluate_intent(intent)

    row = WebOrderIntent(
        session_id=intent.session_id, source_page=intent.source_page,
        service_code=intent.service_code, market=intent.market,
        campaign=intent.campaign or None, customer_id=intent.customer_id,
        whatsapp_number=decision.normalized_number, consent=intent.consent,
        outreach_scheduled=decision.schedule_outreach, outreach_reason=decision.reason)
    db.add(row)
    await db.commit()
    await db.refresh(row)

    if decision.schedule_outreach and decision.normalized_number:
        await _schedule_web_abandonment(intent.session_id, decision.normalized_number, intent.market)

    return {
        "intent_id": row.id,
        "outreach_scheduled": decision.schedule_outreach,
        "reason": decision.reason,
    }
