"""Market + per-market operational config.

Market/CountryConfig are the source of truth for pricing, policies, and
operating hours per country. The LLM must never invent these values - it
only reads them via services.pricing / services.facilities.
"""
import uuid

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Market(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "markets"

    code: Mapped[str] = mapped_column(String(8), unique=True, nullable=False)  # e.g. "AE", "QA"
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    country: Mapped[str] = mapped_column(String(120), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Dubai")
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="AED")
    default_language: Mapped[str] = mapped_column(String(8), nullable=False, default="en")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    country_config: Mapped["CountryConfig | None"] = relationship(
        back_populates="market", uselist=False
    )


class CountryConfig(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "country_configs"

    market_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("markets.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    whatsapp_phone_number: Mapped[str] = mapped_column(String(32), nullable=False)
    default_service_area: Mapped[str] = mapped_column(String(120), nullable=False)
    operating_hours_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    pricing_config_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    policy_config_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    market: Mapped["Market"] = relationship(back_populates="country_config")
