"""Mock WhatsApp channel endpoints.

These simulate what a real WhatsApp webhook/send call would trigger, with
zero external network calls. This is the only supported way to get a
message into (or out of) the system in this task - there is no live
WhatsApp integration.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.classifier.agent import classifier_agent
from app.channels.mock_whatsapp import mock_whatsapp_adapter
from app.db.session import get_db
from app.schemas.message import (
    MockInboundMessage,
    MockInboundResponse,
    MockOutboundMessage,
    MockOutboundResponse,
)

router = APIRouter(prefix="/mock-whatsapp", tags=["mock-whatsapp"])


@router.post("/inbound", response_model=MockInboundResponse)
async def inbound(payload: MockInboundMessage, db: AsyncSession = Depends(get_db)):
    try:
        result = await mock_whatsapp_adapter.receive_inbound(
            db,
            market_code=payload.market_code,
            phone_number=payload.phone_number,
            customer_name=payload.customer_name,
            message=payload.message,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Classifier runs before the WhatsApp Operations Agent (CLAUDE.md §9) -
    # every stored inbound message is labeled immediately, ahead of any
    # later (admin-triggered) agent run on this conversation.
    await classifier_agent.classify(db, conversation_id=uuid.UUID(result.conversation_id))

    await db.commit()
    return MockInboundResponse(
        conversation_id=result.conversation_id,
        message_id=result.message_id,
        customer_id=result.customer_id,
    )


@router.post("/outbound", response_model=MockOutboundResponse)
async def outbound(payload: MockOutboundMessage, db: AsyncSession = Depends(get_db)):
    try:
        result = await mock_whatsapp_adapter.send_outbound(
            db, conversation_id=str(payload.conversation_id), message=payload.message
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await db.commit()
    return MockOutboundResponse(message_id=result.message_id, status=result.status)
