import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

# Full target state machine (see docs/architecture/whatsapp-agent-architecture.md).
# For this MVP the WhatsApp agent may only ever perform draft -> created.
# Every other transition is manual/admin-driven in a later task.
ORDER_STATES = (
    "draft",
    "created",
    "awaiting_pickup",
    "picked_up",
    "processing",
    "ready_for_delivery",
    "out_for_delivery",
    "delivered",
    "cancelled",
    "escalated",
)

# Transitions the agent itself is allowed to perform autonomously.
AGENT_ALLOWED_TRANSITIONS = {
    ("draft", "created"),
}


class Order(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "orders"

    market_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("markets.id", ondelete="RESTRICT"), nullable=False
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
    )
    facility_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("facilities.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    service_type: Mapped[str] = mapped_column(String(64), nullable=False)
    items_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    address_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customer_addresses.id", ondelete="SET NULL"), nullable=True
    )
    pickup_window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pickup_window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivery_window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivery_window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    estimated_total: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    payment_status: Mapped[str] = mapped_column(String(32), nullable=False, default="unpaid")
    source_channel: Mapped[str] = mapped_column(String(32), nullable=False, default="whatsapp")

    events: Mapped[list["OrderEvent"]] = relationship(back_populates="order")


class OrderEvent(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "order_events"

    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False)  # agent | admin | system
    actor_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    order: Mapped["Order"] = relationship(back_populates="events")
