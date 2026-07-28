"""Agent tools for the WhatsApp Operations happy-path agent.

Every tool function:
- reads only from DB/config (never invents prices, policies, or facility data)
- logs its call to AIActionLog via services.audit.log_action
- respects the privacy firewall (services.privacy) for anything that will be
  shown to the LLM or a facility-facing surface

These are the only 10 actions this agent may take. It has no refund,
cancellation, discount, or complaint-resolution tool - those are out of
scope for this task by design.
"""
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.llm import service as llm_service
from app.llm.providers.base import LLMMessage
from app.models.customer import Customer, CustomerAddress
from app.models.facility import Facility
from app.models.human_approval import HumanApproval
from app.models.market import CountryConfig
from app.models.order import Order
from app.services import approvals as approvals_service
from app.services import customers as customers_service
from app.services import facilities as facilities_service
from app.services import orders as orders_service
from app.services import pricing as pricing_service
from app.services.audit import log_action, timed

AGENT_NAME = "whatsapp_operations_agent"

_SERVICE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "wash_and_fold": ("wash and fold", "wash & fold", "wash-fold", "laundry", "wash"),
    "dry_cleaning": ("dry clean", "dry-clean", "dryclean"),
    "ironing": ("iron", "pressing"),
}
_DAY_KEYWORDS: dict[str, str] = {"today": "today", "tonight": "today", "tomorrow": "tomorrow"}
_TIME_OF_DAY_KEYWORDS: tuple[str, ...] = ("morning", "afternoon", "evening")

# Classifier intents (app.agents.classifier.tools.INTENTS) this agent has no
# safe tool for - it can only place/reorder a pickup or answer a general
# question. Anything in this set (or flagged urgent/escalated by sentiment
# alone) skips the happy-path flow entirely in decide_next_action below.
_ESCALATE_ON_INTENTS: frozenset[str] = frozenset(
    {
        "complaint",
        "pickup_issue",
        "delivery_issue",
        "payment_issue",
        "facility_issue",
        "pricing_objection",
        "cancellation",
        "rescheduling",
        "b2b_lead",
        "facility_onboarding",
        "driver_support",
        "lost_lead",
    }
)


def requires_escalation(latest_intent: str | None, latest_urgency: str | None) -> bool:
    """True if the Classifier Agent's most recent labels on this conversation
    (Conversation.latest_intent/latest_urgency, written by
    app.agents.classifier.agent.ClassifierAgent) mean this agent should not
    attempt the happy-path order flow and should escalate to a human
    instead. See CLAUDE.md §6/§8: this agent cannot resolve complaints,
    process refunds/cancellations, or handle B2B/driver/facility enquiries -
    there is no tool for any of that here.
    """
    if latest_urgency in ("urgent", "escalated"):
        return True
    return latest_intent in _ESCALATE_ON_INTENTS


@dataclass
class ToolContext:
    db: AsyncSession
    market_id: uuid.UUID
    conversation_id: uuid.UUID | None = None
    order_id: uuid.UUID | None = None


def extract_order_slots(conversation_text: str, *, known_areas: list[str]) -> dict:
    """Deterministic keyword-based slot extraction over the full inbound
    message history of a conversation. This is NOT the classifier agent
    (that is explicitly out of scope for this task) - it is a simple
    placeholder good enough for the happy-path flow. Replace with the real
    classifier agent in a future task.
    """
    text = conversation_text.lower()
    slots: dict[str, str] = {}

    for service_type, keywords in _SERVICE_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            slots["service_type"] = service_type
            break

    for area in known_areas:
        if area.lower() in text:
            slots["area"] = area
            break

    day = next((normalized for kw, normalized in _DAY_KEYWORDS.items() if kw in text), None)
    if day:
        time_of_day = next((t for t in _TIME_OF_DAY_KEYWORDS if t in text), None)
        slots["pickup_when"] = f"{day} {time_of_day}" if time_of_day else day

    return slots


def compute_pickup_window(pickup_when: str, operating_hours: dict) -> tuple[datetime, datetime]:
    """Pickup window derived from the customer's stated day/time-of-day plus
    the market's configured operating hours - never an invented time.
    """
    now = datetime.now(timezone.utc)
    base_day = now + timedelta(days=1) if pickup_when.startswith("tomorrow") else now

    open_time = operating_hours.get("open", "09:00")
    window_hours = int(operating_hours.get("pickup_window_hours", 3))
    open_hour, open_minute = (int(p) for p in open_time.split(":"))

    start = base_day.replace(hour=open_hour, minute=open_minute, second=0, microsecond=0)
    if "afternoon" in pickup_when:
        start = start.replace(hour=max(open_hour, 13), minute=0)
    elif "evening" in pickup_when:
        start = start.replace(hour=max(open_hour, 17), minute=0)

    end = start + timedelta(hours=window_hours)
    return start, end


async def get_or_create_customer(ctx: ToolContext, *, phone_number: str, name: str | None) -> Customer:
    with timed() as t:
        customer = await customers_service.get_or_create_customer(
            ctx.db, market_id=ctx.market_id, phone_number=phone_number, name=name
        )
    await log_action(
        ctx.db, market_id=ctx.market_id, conversation_id=ctx.conversation_id, order_id=ctx.order_id,
        agent_name=AGENT_NAME, action_type="tool_call", tool_name="get_or_create_customer",
        input_json={"phone_number": phone_number, "name": name},
        output_json={"customer_id": str(customer.id)}, latency_ms=t.ms,
    )
    return customer


async def add_customer_address(
    ctx: ToolContext, *, customer_id: uuid.UUID, address_text: str, area: str | None
) -> CustomerAddress:
    with timed() as t:
        address = await customers_service.add_customer_address(
            ctx.db, customer_id=customer_id, address_text=address_text, area=area
        )
    await log_action(
        ctx.db, market_id=ctx.market_id, conversation_id=ctx.conversation_id, order_id=ctx.order_id,
        agent_name=AGENT_NAME, action_type="tool_call", tool_name="add_customer_address",
        input_json={"customer_id": str(customer_id), "area": area},
        output_json={"address_id": str(address.id)}, latency_ms=t.ms,
    )
    return address


async def get_market_config(ctx: ToolContext) -> CountryConfig | None:
    with timed() as t:
        config = await facilities_service.get_market_config(ctx.db, ctx.market_id)
    await log_action(
        ctx.db, market_id=ctx.market_id, conversation_id=ctx.conversation_id, order_id=ctx.order_id,
        agent_name=AGENT_NAME, action_type="tool_call", tool_name="get_market_config",
        input_json={}, output_json={"found": config is not None}, latency_ms=t.ms,
        success=config is not None,
    )
    return config


async def get_retail_price(ctx: ToolContext, *, pricing_config: dict, service_type: str) -> dict:
    with timed() as t:
        price = pricing_service.get_retail_price(pricing_config, service_type)
    await log_action(
        ctx.db, market_id=ctx.market_id, conversation_id=ctx.conversation_id, order_id=ctx.order_id,
        agent_name=AGENT_NAME, action_type="tool_call", tool_name="get_retail_price",
        input_json={"service_type": service_type}, output_json=price, latency_ms=t.ms,
    )
    return price


async def calculate_order_total(
    ctx: ToolContext, *, pricing_config: dict, service_type: str, quantity: float = 1.0
) -> float:
    with timed() as t:
        total = pricing_service.calculate_order_total(pricing_config, service_type, quantity)
    await log_action(
        ctx.db, market_id=ctx.market_id, conversation_id=ctx.conversation_id, order_id=ctx.order_id,
        agent_name=AGENT_NAME, action_type="tool_call", tool_name="calculate_order_total",
        input_json={"service_type": service_type, "quantity": quantity},
        output_json={"total": total}, latency_ms=t.ms,
    )
    return total


async def create_order(
    ctx: ToolContext,
    *,
    customer_id: uuid.UUID,
    service_type: str,
    address_id: uuid.UUID,
    pickup_window_start: datetime,
    pickup_window_end: datetime,
    estimated_total: float,
) -> Order:
    with timed() as t:
        order = await orders_service.create_draft_order(
            ctx.db,
            market_id=ctx.market_id,
            customer_id=customer_id,
            service_type=service_type,
            items_json={"service_type": service_type},
            address_id=address_id,
            pickup_window_start=pickup_window_start,
            pickup_window_end=pickup_window_end,
            estimated_total=estimated_total,
            source_channel="whatsapp",
        )
        order = await orders_service.transition_order(
            ctx.db, order=order, to_status="created",
            actor_type="agent", actor_id=AGENT_NAME,
        )
    await log_action(
        ctx.db, market_id=ctx.market_id, conversation_id=ctx.conversation_id, order_id=order.id,
        agent_name=AGENT_NAME, action_type="tool_call", tool_name="create_order",
        input_json={"customer_id": str(customer_id), "service_type": service_type,
                    "estimated_total": estimated_total},
        output_json={"order_id": str(order.id), "status": order.status}, latency_ms=t.ms,
    )
    return order


async def assign_facility_to_order(
    ctx: ToolContext, *, order: Order, area: str | None
) -> Facility | None:
    with timed() as t:
        facility = await facilities_service.find_facility_for_area(
            ctx.db, market_id=ctx.market_id, area=area
        )
        if facility is not None:
            await orders_service.assign_facility(
                ctx.db, order=order, facility_id=facility.id,
                actor_type="agent", actor_id=AGENT_NAME,
            )
    await log_action(
        ctx.db, market_id=ctx.market_id, conversation_id=ctx.conversation_id, order_id=order.id,
        agent_name=AGENT_NAME, action_type="tool_call", tool_name="assign_facility_to_order",
        input_json={"area": area},
        output_json={"facility_id": str(facility.id) if facility else None},
        latency_ms=t.ms, success=facility is not None,
    )
    return facility


async def draft_customer_reply(ctx: ToolContext, *, draft_text: str) -> str:
    """Passes the deterministically-built draft_text through the LLM gateway
    (MockProvider echoes it back) so the call is audited like any other LLM
    use, then logs the tool call itself.
    """
    with timed() as t:
        result = await llm_service.complete(
            ctx.db,
            market_id=ctx.market_id,
            agent_name=AGENT_NAME,
            conversation_id=ctx.conversation_id,
            order_id=ctx.order_id,
            messages=[LLMMessage(role="user", content=draft_text)],
            tier="routine",
        )
    await log_action(
        ctx.db, market_id=ctx.market_id, conversation_id=ctx.conversation_id, order_id=ctx.order_id,
        agent_name=AGENT_NAME, action_type="tool_call", tool_name="draft_customer_reply",
        input_json={"draft_text": draft_text}, output_json={"text": result.text}, latency_ms=t.ms,
    )
    return result.text


async def create_approval_request(
    ctx: ToolContext, *, action_type: str, proposed_payload: dict, reason: str | None = None
) -> HumanApproval:
    with timed() as t:
        approval = await approvals_service.create_approval_request(
            ctx.db, market_id=ctx.market_id, requested_by_agent=AGENT_NAME,
            action_type=action_type, proposed_payload=proposed_payload, reason=reason,
            conversation_id=ctx.conversation_id, order_id=ctx.order_id,
        )
    await log_action(
        ctx.db, market_id=ctx.market_id, conversation_id=ctx.conversation_id, order_id=ctx.order_id,
        agent_name=AGENT_NAME, action_type="tool_call", tool_name="create_approval_request",
        input_json={"action_type": action_type, "reason": reason},
        output_json={"approval_id": str(approval.id)}, latency_ms=t.ms,
    )
    return approval


async def escalate_to_human(
    ctx: ToolContext, *, reason: str, draft_text: str | None = None
) -> HumanApproval:
    with timed() as t:
        approval = await approvals_service.create_approval_request(
            ctx.db, market_id=ctx.market_id, requested_by_agent=AGENT_NAME,
            action_type="escalate_to_human",
            proposed_payload={"text": draft_text} if draft_text else {},
            reason=reason, conversation_id=ctx.conversation_id, order_id=ctx.order_id,
        )
    await log_action(
        ctx.db, market_id=ctx.market_id, conversation_id=ctx.conversation_id, order_id=ctx.order_id,
        agent_name=AGENT_NAME, action_type="tool_call", tool_name="escalate_to_human",
        input_json={"reason": reason}, output_json={"approval_id": str(approval.id)}, latency_ms=t.ms,
    )
    return approval
