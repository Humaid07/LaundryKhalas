"""Shared persistence helpers used by both the local test-chat endpoint and
the WhatsApp webhook endpoint, so conversation/message/log handling stays
identical regardless of channel.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import AgentLog, Conversation, Message


async def get_or_create_conversation(
    db: AsyncSession,
    *,
    conversation_id: str | None,
    channel: str,
    customer_phone: str | None = None,
    customer_name: str | None = None,
) -> Conversation:
    if conversation_id:
        result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
        existing = result.scalar_one_or_none()
        if existing:
            return existing

    if not conversation_id and customer_phone:
        result = await db.execute(
            select(Conversation).where(
                Conversation.channel == channel,
                Conversation.customer_phone == customer_phone,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing

    conversation = Conversation(
        channel=channel, customer_phone=customer_phone, customer_name=customer_name
    )
    db.add(conversation)
    await db.flush()
    return conversation


async def add_message(
    db: AsyncSession,
    *,
    conversation_id: str,
    direction: str,
    sender_type: str,
    text: str,
    domain_status: str | None = None,
    raw_payload_json: dict | None = None,
) -> Message:
    message = Message(
        conversation_id=conversation_id,
        direction=direction,
        sender_type=sender_type,
        text=text,
        domain_status=domain_status,
        raw_payload_json=raw_payload_json,
    )
    db.add(message)
    await db.flush()
    return message


async def add_agent_log(
    db: AsyncSession,
    *,
    conversation_id: str,
    message_id: str | None,
    action: str,
    input_json: dict | None,
    output_json: dict | None,
    provider: str | None,
    model: str | None,
    success: bool,
    error_message: str | None = None,
) -> AgentLog:
    log = AgentLog(
        conversation_id=conversation_id,
        message_id=message_id,
        action=action,
        input_json=input_json,
        output_json=output_json,
        provider=provider,
        model=model,
        success=success,
        error_message=error_message,
    )
    db.add(log)
    await db.flush()
    return log


async def list_messages(db: AsyncSession, *, conversation_id: str) -> list[Message]:
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    return list(result.scalars().all())
