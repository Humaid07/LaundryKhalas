"""Minimal storage for the standalone agent. Deliberately not the full
order-management schema from the main backend - just enough to hold a
conversation thread, its messages, and an audit trail of what the agent did.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
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
    # How the pickup address was captured (spec §29): customer | typed | whatsapp_location |
    # saved_reuse (a returning customer reused their saved address).
    address_source: Mapped[str | None] = mapped_column(String(24), nullable=True)
    pickup_date: Mapped[str | None] = mapped_column(String(60), nullable=True)
    pickup_time: Mapped[str | None] = mapped_column(String(60), nullable=True)
    city: Mapped[str | None] = mapped_column(String(60), nullable=True)
    delivery_preference: Mapped[str | None] = mapped_column(String(60), nullable=True)

    status: Mapped[str] = mapped_column(String(30), default="draft")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    change_request: Mapped[str | None] = mapped_column(Text, nullable=True)

    amount: Mapped[float | None] = mapped_column(nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="AED")

    # Order-discount snapshot (spec §§15, 29). Backend-authoritative; mirrors the
    # Supabase orders columns. eligible_subtotal is the pre-discount total; reason is
    # the discount rule that applied (e.g. STANDARD_OVER_100, NEGOTIATED, PRICE_PUSHBACK).
    eligible_subtotal: Mapped[float | None] = mapped_column(nullable=True)
    discount_percentage: Mapped[float | None] = mapped_column(nullable=True)
    discount_amount: Mapped[float | None] = mapped_column(nullable=True)
    discount_rule_code: Mapped[str | None] = mapped_column(String(48), nullable=True)
    # The WhatsApp service rule-set version the order's pricing was produced under
    # (spec §§17, 29). Stamped at confirmation so a price traces to its exact rules.
    rule_version: Mapped[str | None] = mapped_column(String(24), nullable=True)
    facility: Mapped[str | None] = mapped_column(String(120), nullable=True)
    driver: Mapped[str | None] = mapped_column(String(120), nullable=True)
    payment: Mapped[str | None] = mapped_column(String(60), nullable=True)

    # Stripe-first payment state (spec §13). Backend-authoritative; the model never
    # sets these directly. Timestamps double as the "explained/requested/accepted"
    # flags (non-null = it happened). Migration 000040 mirrors these on Supabase.
    payment_preference: Mapped[str] = mapped_column(String(20), default="UNDECIDED")
    stripe_preference_explained_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    stripe_no_account_explained_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    cash_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    cash_accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)
    payment_followup_stage: Mapped[int] = mapped_column(default=0)

    # Stripe Invoicing linkage (spec §13, Phase 2b live-payments). Set by the
    # payments gateway when a hosted VAT invoice is created for a STRIPE order, and
    # by the /webhooks/stripe handler when Stripe reports payment. payment_status
    # follows the vocabulary in services/payments/base.py (unpaid|pending|paid|
    # failed|refunded|void). amount_paid_minor is in minor units (fils/cents).
    # Migration 000041 mirrors these on Supabase.
    stripe_customer_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    stripe_invoice_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    stripe_hosted_invoice_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    stripe_invoice_pdf_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    payment_status: Mapped[str] = mapped_column(String(20), default="unpaid")
    amount_paid_minor: Mapped[int | None] = mapped_column(nullable=True)
    payment_currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)

    source_channel: Mapped[str] = mapped_column(String(20), default="whatsapp")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ScheduledFollowup(Base):
    """A pending customer follow-up (spec §§14, 24, 25). The scheduler POLICY lives in
    services/followups.py (pure); this is the durable queue a sweeper reads. One row per
    (conversation, follow-up type) — `dedupe_key` is unique so a follow-up is scheduled at
    most once. `status`: PENDING | SENT | CANCELLED | SUPPRESSED. Migration 000042 mirrors
    these on Supabase. `is_demo` never applies here — these drive real outreach only when a
    live provider + window allow it.
    """

    __tablename__ = "scheduled_followups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    conversation_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    order_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    customer_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)

    followup_type: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), default="PENDING")
    template_id: Mapped[str | None] = mapped_column(String(48), nullable=True)
    dedupe_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)

    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    anchor_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    market: Mapped[str] = mapped_column(String(8), default="AE")
    persona: Mapped[str | None] = mapped_column(String(40), nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    suppressed_reason: Mapped[str | None] = mapped_column(String(48), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WebOrderIntent(Base):
    """A website "Order Now" click (spec §24). Always recorded for analytics; abandonment
    outreach is scheduled ONLY when the visitor is identified + consented + has a verified
    WhatsApp number (see services/web_order_intent). Never fingerprint a number. Migration
    000043 mirrors these on Supabase.
    """

    __tablename__ = "web_order_intents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    source_page: Mapped[str | None] = mapped_column(String(255), nullable=True)
    service_code: Mapped[str | None] = mapped_column(String(60), nullable=True)
    market: Mapped[str] = mapped_column(String(8), default="AE")
    campaign: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    customer_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    whatsapp_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    consent: Mapped[bool] = mapped_column(Boolean, default=False)
    outreach_scheduled: Mapped[bool] = mapped_column(Boolean, default=False)
    outreach_reason: Mapped[str | None] = mapped_column(String(48), nullable=True)
    converted: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class CatalogueVersion(Base):
    """A publishable snapshot of the whole item catalogue. Admins edit a DRAFT
    version's items without touching live pricing, then PUBLISH it atomically;
    runtime consumers read exactly one `is_current` published version per market.
    Rollback creates a NEW published version copying an older one (never deletes).
    """

    __tablename__ = "catalogue_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    version_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft|pending_review|published|archived
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
    market: Mapped[str] = mapped_column(String(8), default="AE")
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String(30), nullable=True)  # admin_edit|import|rollback|seed
    rollback_of_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    published_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    effective_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    items: Mapped[list["CatalogueVersionItem"]] = relationship(
        back_populates="version", cascade="all, delete-orphan"
    )


class CatalogueVersionItem(Base):
    """The immutable per-item price row for one catalogue version."""

    __tablename__ = "catalogue_version_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    version_id: Mapped[str] = mapped_column(ForeignKey("catalogue_versions.id"))
    item_code: Mapped[str] = mapped_column(String(80), index=True)
    category_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    category_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    service_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    service_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    canonical_name: Mapped[str] = mapped_column(String(160))
    display_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    pricing_type: Mapped[str] = mapped_column(String(40), default="FIXED_PER_ITEM")
    pricing_unit: Mapped[str] = mapped_column(String(20), default="ITEM")
    current_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    regular_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="AED")
    is_starting_price: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_inspection: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_measurement: Mapped[bool] = mapped_column(Boolean, default=False)
    vat_rate: Mapped[float] = mapped_column(Float, default=0.05)
    # Published Laundry Khalas prices are already final VAT-inclusive customer
    # prices — the customer pays the stored price with NO 5% added (spec §§1-4).
    prices_include_vat: Mapped[bool] = mapped_column(Boolean, default=True)
    market: Mapped[str] = mapped_column(String(8), default="AE")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    disclaimer: Mapped[str | None] = mapped_column(Text, nullable=True)  # customer-facing
    internal_note: Mapped[str | None] = mapped_column(Text, nullable=True)  # NEVER public
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    version: Mapped["CatalogueVersion"] = relationship(back_populates="items")


class PricingPromotion(Base):
    """A time-bounded promotional overlay on a published item price. Resolved at
    runtime by the price resolver (never overwrites the base/regular price)."""

    __tablename__ = "pricing_promotions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    item_code: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    promo_price: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8), default="AED")
    market: Mapped[str] = mapped_column(String(8), default="AE")
    priority: Mapped[int] = mapped_column(Integer, default=0)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class PricingAuditLog(Base):
    """Immutable record of every material pricing change (never overwritten)."""

    __tablename__ = "pricing_audit_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    action: Mapped[str] = mapped_column(String(30))
    entity_type: Mapped[str] = mapped_column(String(20))  # item|version|promotion
    entity_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)
    field: Mapped[str | None] = mapped_column(String(60), nullable=True)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor: Mapped[str | None] = mapped_column(String(120), nullable=True)
    version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class PricingSyncStatus(Base):
    """Record of a website/cache sync attempt after a publish (§14/§19)."""

    __tablename__ = "pricing_sync_status"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    target: Mapped[str] = mapped_column(String(30))  # website|whatsapp_cache
    version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    version_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20))  # success|failed|pending
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


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
