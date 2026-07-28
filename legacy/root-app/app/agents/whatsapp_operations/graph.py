"""LangGraph orchestration for the WhatsApp Operations happy-path agent.

Flow: load_conversation_context -> assemble_safe_context -> decide_next_action
-> execute_tool_loop (capped) -> safety_filter -> draft_reply ->
create_approval -> END.

This agent supports exactly one flow: a customer wants a laundry pickup and
either (a) more info is needed, so the agent asks a follow-up question, or
(b) enough info exists, so the agent creates a mock order, assigns a mock
facility, and drafts a confirmation. Every generated reply - follow-up or
confirmation - is queued as a HumanApproval; nothing is ever sent
automatically. No refunds, cancellations, discounts, or complaint handling
are possible here - there is no tool for any of that.
"""
from __future__ import annotations

import uuid
from typing import TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.whatsapp_operations import prompts, tools
from app.core.config import get_settings
from app.models.conversation import Conversation
from app.models.customer import Customer
from app.models.message import Message
from app.services import facilities as facilities_service
from app.services import pricing as pricing_service
from app.services.privacy import customer_context_for_llm


class AgentState(TypedDict, total=False):
    conversation_id: str
    market_id: str
    customer_id: str
    customer_phone: str
    customer_name: str | None
    conversation_text: str
    known_areas: list[str]
    latest_intent: str | None
    latest_urgency: str | None
    slots: dict
    missing_fields: list[str]
    decision: str  # "ask_followup" | "create_order" | "escalate"
    tool_steps: int
    order_id: str | None
    facility_id: str | None
    facility_name: str | None
    estimated_total: float | None
    currency: str
    safety_ok: bool
    safety_reason: str | None
    draft_reply_text: str | None
    approval_id: str | None
    error: str | None


def build_graph(db: AsyncSession):
    """Builds a fresh compiled graph bound to the given DB session. A new
    graph is built per agent run (cheap - it's just closures over `db`) so
    every node shares one transaction.
    """

    async def load_conversation_context(state: AgentState) -> AgentState:
        conv_id = uuid.UUID(state["conversation_id"])
        result = await db.execute(select(Conversation).where(Conversation.id == conv_id))
        conversation = result.scalar_one_or_none()
        if conversation is None:
            return {**state, "decision": "escalate", "error": "conversation_not_found"}

        if conversation.manual_takeover:
            return {**state, "decision": "escalate", "error": "manual_takeover_active"}

        cust_result = await db.execute(
            select(Customer).where(Customer.id == conversation.customer_id)
        )
        customer = cust_result.scalar_one_or_none()

        msgs_result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conv_id, Message.direction == "inbound")
            .order_by(Message.created_at)
        )
        conversation_text = "\n".join(m.text for m in msgs_result.scalars().all())

        known_areas = await facilities_service.list_known_areas(
            db, market_id=conversation.market_id
        )

        return {
            **state,
            "market_id": str(conversation.market_id),
            "customer_id": str(conversation.customer_id),
            "customer_phone": customer.phone_number if customer else "",
            "customer_name": customer.name if customer else None,
            "conversation_text": conversation_text,
            "known_areas": known_areas,
            "latest_intent": conversation.latest_intent,
            "latest_urgency": conversation.latest_urgency,
        }

    async def assemble_safe_context(state: AgentState) -> AgentState:
        # Privacy firewall checkpoint: nothing beyond name/area/language is
        # ever passed to draft_reply's LLM call - see draft_reply below,
        # which builds its prompt only from customer_context_for_llm().
        return state

    async def decide_next_action(state: AgentState) -> AgentState:
        if state.get("decision") == "escalate":
            return state

        # Classifier-driven guard (CLAUDE.md §9: classifier runs before this
        # agent). If the latest inbound message was flagged as a complaint,
        # cancellation, rescheduling, payment issue, B2B lead, or otherwise
        # urgent/escalated, do not attempt slot extraction at all - this
        # agent has no tool for any of those, and running the happy-path
        # flow anyway risks a tone-deaf follow-up question or, worse,
        # accidentally creating a duplicate order if a day/area keyword also
        # appears in the message (e.g. a reschedule request). Escalate
        # straight to a human instead - see
        # docs/architecture/classifier-agent.md.
        if tools.requires_escalation(state.get("latest_intent"), state.get("latest_urgency")):
            return {
                **state,
                "decision": "escalate",
                "error": f"classifier_flagged_intent={state.get('latest_intent')}",
            }

        slots = tools.extract_order_slots(
            state.get("conversation_text", ""), known_areas=state.get("known_areas", [])
        )
        missing = [f for f in ("service_type", "area", "pickup_when") if not slots.get(f)]
        decision = "create_order" if not missing else "ask_followup"
        return {**state, "slots": slots, "missing_fields": missing, "decision": decision}

    async def execute_tool_loop(state: AgentState) -> AgentState:
        if state.get("decision") != "create_order":
            return state

        settings = get_settings()
        run_ctx = tools.ToolContext(
            db=db,
            market_id=uuid.UUID(state["market_id"]),
            conversation_id=uuid.UUID(state["conversation_id"]),
        )
        slots = state["slots"]
        steps = 0

        def _cap_exceeded(n: int) -> bool:
            return n > settings.cost_max_tool_steps_per_run

        try:
            steps += 1
            customer = await tools.get_or_create_customer(
                run_ctx, phone_number=state["customer_phone"], name=state.get("customer_name")
            )

            steps += 1
            address = await tools.add_customer_address(
                run_ctx,
                customer_id=customer.id,
                address_text=state.get("conversation_text", ""),
                area=slots["area"],
            )

            steps += 1
            market_config = await tools.get_market_config(run_ctx)
            if market_config is None:
                return {**state, "decision": "escalate", "error": "market_not_configured",
                        "tool_steps": steps}

            steps += 1
            try:
                total = await tools.calculate_order_total(
                    run_ctx,
                    pricing_config=market_config.pricing_config_json,
                    service_type=slots["service_type"],
                )
            except pricing_service.PriceNotConfigured as exc:
                return {**state, "decision": "escalate", "error": str(exc), "tool_steps": steps}

            if _cap_exceeded(steps):
                return {**state, "decision": "escalate", "error": "tool_step_limit_exceeded",
                        "tool_steps": steps}

            steps += 1
            pickup_start, pickup_end = tools.compute_pickup_window(
                slots["pickup_when"], market_config.operating_hours_json
            )
            order = await tools.create_order(
                run_ctx,
                customer_id=customer.id,
                service_type=slots["service_type"],
                address_id=address.id,
                pickup_window_start=pickup_start,
                pickup_window_end=pickup_end,
                estimated_total=total,
            )

            steps += 1
            facility = await tools.assign_facility_to_order(run_ctx, order=order, area=slots["area"])
            if facility is None:
                return {**state, "decision": "escalate", "error": "no_facility_available",
                        "order_id": str(order.id), "tool_steps": steps}

            if _cap_exceeded(steps):
                return {**state, "decision": "escalate", "error": "tool_step_limit_exceeded",
                        "order_id": str(order.id), "tool_steps": steps}

            market = await facilities_service.get_market(db, uuid.UUID(state["market_id"]))

            return {
                **state,
                "order_id": str(order.id),
                "facility_id": str(facility.id),
                "facility_name": facility.name,
                "estimated_total": total,
                "currency": market.currency if market else "AED",
                "tool_steps": steps,
            }
        except Exception as exc:  # noqa: BLE001 - any tool failure escalates, never half-completes silently
            return {**state, "decision": "escalate", "error": str(exc), "tool_steps": steps}

    async def safety_filter(state: AgentState) -> AgentState:
        if state.get("decision") == "escalate":
            return {**state, "safety_ok": False, "safety_reason": state.get("error")}

        if state.get("decision") == "create_order" and not (
            state.get("order_id") and state.get("facility_id")
        ):
            return {
                **state,
                "decision": "escalate",
                "safety_ok": False,
                "safety_reason": "incomplete_order_state",
                "error": "incomplete_order_state",
            }

        return {**state, "safety_ok": True, "safety_reason": None}

    async def draft_reply(state: AgentState) -> AgentState:
        run_ctx = tools.ToolContext(
            db=db,
            market_id=uuid.UUID(state["market_id"]),
            conversation_id=uuid.UUID(state["conversation_id"]),
            order_id=uuid.UUID(state["order_id"]) if state.get("order_id") else None,
        )
        safe_ctx = customer_context_for_llm(
            name=state.get("customer_name"),
            area=(state.get("slots") or {}).get("area"),
            city=None,
            preferred_language="en",
        )

        if state.get("decision") == "escalate":
            text = prompts.render_escalation_notice(safe_ctx)
        elif state.get("decision") == "create_order":
            text = prompts.render_confirmation(
                safe_ctx,
                service_type=state["slots"]["service_type"],
                pickup_when=state["slots"]["pickup_when"],
                total=state["estimated_total"],
                currency=state.get("currency", "AED"),
                facility_name=state.get("facility_name", "our partner facility"),
            )
        else:
            text = prompts.render_followup_question(
                safe_ctx, missing_fields=state.get("missing_fields", [])
            )

        result_text = await tools.draft_customer_reply(run_ctx, draft_text=text)
        return {**state, "draft_reply_text": result_text}

    async def create_approval(state: AgentState) -> AgentState:
        run_ctx = tools.ToolContext(
            db=db,
            market_id=uuid.UUID(state["market_id"]),
            conversation_id=uuid.UUID(state["conversation_id"]),
            order_id=uuid.UUID(state["order_id"]) if state.get("order_id") else None,
        )

        if state.get("decision") == "escalate":
            approval = await tools.escalate_to_human(
                run_ctx,
                reason=state.get("error") or "escalation_required",
                draft_text=state.get("draft_reply_text"),
            )
        else:
            approval = await tools.create_approval_request(
                run_ctx,
                action_type="send_customer_reply",
                proposed_payload={"text": state.get("draft_reply_text")},
                reason=f"agent_decision={state.get('decision')}",
            )
        return {**state, "approval_id": str(approval.id)}

    graph = StateGraph(AgentState)
    graph.add_node("load_conversation_context", load_conversation_context)
    graph.add_node("assemble_safe_context", assemble_safe_context)
    graph.add_node("decide_next_action", decide_next_action)
    graph.add_node("execute_tool_loop", execute_tool_loop)
    graph.add_node("safety_filter", safety_filter)
    graph.add_node("draft_reply", draft_reply)
    graph.add_node("create_approval", create_approval)

    graph.set_entry_point("load_conversation_context")
    graph.add_edge("load_conversation_context", "assemble_safe_context")
    graph.add_edge("assemble_safe_context", "decide_next_action")
    graph.add_edge("decide_next_action", "execute_tool_loop")
    graph.add_edge("execute_tool_loop", "safety_filter")
    graph.add_edge("safety_filter", "draft_reply")
    graph.add_edge("draft_reply", "create_approval")
    graph.add_edge("create_approval", END)

    return graph.compile()
