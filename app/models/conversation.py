import uuid

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Conversation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "conversations"

    market_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("markets.id", ondelete="RESTRICT"), nullable=False
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
    )
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="whatsapp")
    external_thread_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    assigned_to_user_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    manual_takeover: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Placeholder fields for future classifier agent (not built in this task).
    latest_intent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    latest_sentiment: Mapped[str | None] = mapped_column(String(32), nullable=True)
    latest_urgency: Mapped[str | None] = mapped_column(String(32), nullable=True)

    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", order_by="Message.created_at"
    )
