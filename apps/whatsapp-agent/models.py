"""Minimal storage for the standalone agent. Deliberately not the full
order-management schema from the main backend - just enough to hold a
conversation thread, its messages, and an audit trail of what the agent did.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    channel: Mapped[str] = mapped_column(String(20), default="local")  # local | whatsapp
    customer_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    customer_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", order_by="Message.created_at"
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"))
    direction: Mapped[str] = mapped_column(String(10))  # inbound | outbound
    sender_type: Mapped[str] = mapped_column(String(20))  # customer | agent | system
    text: Mapped[str] = mapped_column(Text)
    domain_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    raw_payload_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")


class Order(Base):
    """A mock/demo order the WhatsApp conversation builds up and mutates
    behind the scenes. This is the state a future dashboard reads from - the
    whole point is that the chat doesn't just reply, it updates a real,
    queryable order row (draft -> active -> ... -> completed/cancelled).

    Every row is demo data (`is_demo` defaults True); nothing here is a live
    operational order. `order_id` is the human/business id shown in chat
    (e.g. "LK-AE-1024"); `id` is the internal uuid primary key.
    """

    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    order_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)

    conversation_id: Mapped[str | None] = mapped_column(
        ForeignKey("conversations.id"), nullable=True
    )
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    customer_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    customer_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)

    service_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    items: Mapped[list | None] = mapped_column(JSON, default=list)
    pickup_area: Mapped[str | None] = mapped_column(String(120), nullable=True)
    pickup_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pickup_date: Mapped[str | None] = mapped_column(String(60), nullable=True)
    pickup_time: Mapped[str | None] = mapped_column(String(60), nullable=True)
    city: Mapped[str | None] = mapped_column(String(60), nullable=True)
    delivery_preference: Mapped[str | None] = mapped_column(String(60), nullable=True)

    status: Mapped[str] = mapped_column(String(30), default="draft")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    change_request: Mapped[str | None] = mapped_column(Text, nullable=True)

    amount: Mapped[float | None] = mapped_column(nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="AED")
    facility: Mapped[str | None] = mapped_column(String(120), nullable=True)
    driver: Mapped[str | None] = mapped_column(String(120), nullable=True)
    payment: Mapped[str | None] = mapped_column(String(60), nullable=True)

    source_channel: Mapped[str] = mapped_column(String(20), default="whatsapp")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AgentLog(Base):
    __tablename__ = "agent_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id"))
    message_id: Mapped[str | None] = mapped_column(
        ForeignKey("messages.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(40))
    input_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    provider: Mapped[str | None] = mapped_column(String(20), nullable=True)
    model: Mapped[str | None] = mapped_column(String(60), nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
