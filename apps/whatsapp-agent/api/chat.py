from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from agents.whatsapp_agent.agent import handle_message
from db import get_db
from schemas import MessageRead, TestChatRequest, TestChatResponse
from services import storage
from services.privacy import mask_pii
from settings import get_settings

router = APIRouter(tags=["test-chat"])


@router.post("/api/test-chat/message", response_model=TestChatResponse)
async def send_test_message(payload: TestChatRequest, db: AsyncSession = Depends(get_db)):
    settings = get_settings()
    conversation = await storage.get_or_create_conversation(
        db,
        conversation_id=payload.conversation_id,
        channel="local",
        customer_phone=payload.phone_number,
        customer_name=payload.sender_name,
    )

    history_rows = await storage.list_messages(db, conversation_id=conversation.id)
    history = [
        ("customer" if m.direction == "inbound" else "agent", m.text) for m in history_rows
    ]

    inbound = await storage.add_message(
        db,
        conversation_id=conversation.id,
        direction="inbound",
        sender_type="customer",
        text=payload.message,
    )

    reply = await handle_message(
        text=payload.message,
        history=history,
        action_id=payload.action_id,
        db=db,
        conversation=conversation,
    )

    outbound = await storage.add_message(
        db,
        conversation_id=conversation.id,
        direction="outbound",
        sender_type="agent",
        text=reply.text,
        domain_status=reply.domain,
    )
    inbound.domain_status = reply.domain

    llm_mode = "live" if settings.live_llm_ready else "mock"
    # RULE 8 — mask PII (phone/email) before it enters the audit log. The raw
    # conversation transcript in the messages table stays intact for context.
    await storage.add_agent_log(
        db,
        conversation_id=conversation.id,
        message_id=outbound.id,
        action="handoff" if reply.handoff else "agent_reply",
        input_json={
            "message": mask_pii(payload.message),
            "intent": reply.intent,
            "action_id": payload.action_id,
        },
        output_json={
            "reply": mask_pii(reply.text),
            "domain": reply.domain,
            "actions": [a.id for a in reply.actions],
            "handoff": reply.handoff,
            "order_id": reply.order_id,
            "order_status": reply.order_status,
            "llm_mode": llm_mode,
            "whatsapp_mode": settings.whatsapp_mode,
        },
        provider=reply.provider,
        model=reply.model,
        success=reply.success,
        error_message=reply.error_message,
    )

    await db.commit()

    return TestChatResponse(
        conversation_id=conversation.id,
        user_message=payload.message,
        agent_reply=reply.text,
        domain=reply.domain,
        mode="live" if settings.live_llm_ready else "mock",
        provider=reply.provider,
        actions=[a.to_dict() for a in reply.actions],
        order_id=reply.order_id,
        order_status=reply.order_status,
    )


@router.get("/api/messages", response_model=list[MessageRead])
async def get_messages(conversation_id: str, db: AsyncSession = Depends(get_db)):
    return await storage.list_messages(db, conversation_id=conversation_id)
