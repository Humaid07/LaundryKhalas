"""OperationsHappyPathAgent - entry point for the WhatsApp Operations agent.

Supports exactly one flow: ask a follow-up question when info is missing,
or create a mock order + assign a mock facility + draft a confirmation when
it isn't. Every reply is queued for admin approval; nothing is auto-sent.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.whatsapp_operations.graph import AgentState, build_graph
from app.models.conversation import Conversation
from app.services.audit import log_action

AGENT_NAME = "whatsapp_operations_agent"


class ManualTakeoverActive(Exception):
    pass


class ConversationNotFound(Exception):
    pass


class OperationsHappyPathAgent:
    async def run(self, db: AsyncSession, *, conversation_id: uuid.UUID) -> AgentState:
        result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
        conversation = result.scalar_one_or_none()
        if conversation is None:
            raise ConversationNotFound(f"Conversation {conversation_id} not found")
        if conversation.manual_takeover:
            raise ManualTakeoverActive(
                f"Conversation {conversation_id} is under manual takeover; agent will not run."
            )

        graph = build_graph(db)
        initial_state: AgentState = {"conversation_id": str(conversation_id)}
        final_state: AgentState = await graph.ainvoke(initial_state)

        order_id = final_state.get("order_id")
        await log_action(
            db,
            market_id=conversation.market_id,
            conversation_id=conversation_id,
            order_id=uuid.UUID(order_id) if order_id else None,
            agent_name=AGENT_NAME,
            action_type="agent_run",
            input_json={"conversation_id": str(conversation_id)},
            output_json={
                "decision": final_state.get("decision"),
                "approval_id": final_state.get("approval_id"),
                "order_id": order_id,
            },
            success=bool(final_state.get("approval_id")),
        )
        return final_state


operations_happy_path_agent = OperationsHappyPathAgent()
