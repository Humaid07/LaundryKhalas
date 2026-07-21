"""Mock WhatsApp channel adapter.

Persists inbound/outbound messages exactly like a live channel would, but
makes zero external network calls. This is the only adapter enabled by
default. Get-or-create customer/conversation, store message, done.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.channels.base import InboundResult, OutboundResult, WhatsAppChannel
from app.models.conversation import Conversation
from app.models.message import Message
from app.services.customers import get_market_by_code, get_or_create_customer


class MockWhatsAppAdapter(WhatsAppChannel):
    async def receive_inbound(
        self,
        db: AsyncSession,
        *,
        market_code: str,
        phone_number: str,
        customer_name: str | None,
        message: str,
    ) -> InboundResult:
        market = await get_market_by_code(db, market_code)
        if market is None:
            raise ValueError(f"Unknown market_code={market_code!r}")

        customer = await get_or_create_customer(
            db, market_id=market.id, phone_number=phone_number, name=customer_name
        )

        conversation = await self._get_or_create_open_conversation(
            db, market_id=market.id, customer_id=customer.id
        )

        msg = Message(
            conversation_id=conversation.id,
            direction="inbound",
            sender_type="customer",
            text=message,
            raw_payload_json={
                "market_code": market_code,
                "phone_number": phone_number,
                "customer_name": customer_name,
            },
            status="received",
        )
        db.add(msg)
        await db.flush()

        return InboundResult(
            conversation_id=str(conversation.id),
            message_id=str(msg.id),
            customer_id=str(customer.id),
        )

    async def send_outbound(
        self, db: AsyncSession, *, conversation_id: str, message: str
    ) -> OutboundResult:
        conv_uuid = uuid.UUID(conversation_id)
        result = await db.execute(select(Conversation).where(Conversation.id == conv_uuid))
        conversation = result.scalar_one_or_none()
        if conversation is None:
            raise ValueError(f"Unknown conversation_id={conversation_id!r}")

        msg = Message(
            conversation_id=conversation.id,
            direction="outbound",
            sender_type="agent",
            text=message,
            raw_payload_json={},
            status="mock_sent",
        )
        db.add(msg)
        await db.flush()

        return OutboundResult(message_id=str(msg.id), status="mock_sent")

    async def _get_or_create_open_conversation(
        self, db: AsyncSession, *, market_id: uuid.UUID, customer_id: uuid.UUID
    ) -> Conversation:
        result = await db.execute(
            select(Conversation)
            .where(
                Conversation.market_id == market_id,
                Conversation.customer_id == customer_id,
                Conversation.status == "open",
            )
            .order_by(Conversation.created_at.desc())
        )
        conversation = result.scalars().first()
        if conversation:
            return conversation

        conversation = Conversation(
            market_id=market_id,
            customer_id=customer_id,
            channel="whatsapp",
            status="open",
        )
        db.add(conversation)
        await db.flush()
        return conversation


mock_whatsapp_adapter = MockWhatsAppAdapter()
