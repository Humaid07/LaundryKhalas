"""ClassifierAgent - entry point for the Classifier Agent.

Per CLAUDE.md §9, this runs before the WhatsApp Operations Agent. It reads
the newest inbound message on a conversation, classifies it
(intent/sentiment/sales-stage/topic) plus derives the routing flags listed
in CLAUDE.md §9 (urgency, complaint, angry, escalation, refund/cancellation,
B2B), writes the three existing `Conversation.latest_intent/
latest_sentiment/latest_urgency` placeholder columns, and logs the full
result to AIActionLog. It creates no order, sends no reply, and requests no
approval - it only observes and labels.
"""
from __future__ import annotations

import json
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.classifier import tools
from app.llm import service as llm_service
from app.llm.providers.base import LLMMessage
from app.models.conversation import Conversation
from app.models.message import Message
from app.services.audit import log_action, timed

AGENT_NAME = "classifier_agent"


class ClassifierConversationNotFound(Exception):
    pass


class NoInboundMessageToClassify(Exception):
    pass


class ClassifierAgent:
    async def classify(self, db: AsyncSession, *, conversation_id: uuid.UUID) -> dict:
        result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
        conversation = result.scalar_one_or_none()
        if conversation is None:
            raise ClassifierConversationNotFound(f"Conversation {conversation_id} not found")

        latest_result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id, Message.direction == "inbound")
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        latest_message = latest_result.scalar_one_or_none()
        if latest_message is None:
            raise NoInboundMessageToClassify(
                f"Conversation {conversation_id} has no inbound message to classify"
            )

        count_result = await db.execute(
            select(func.count(Message.id)).where(
                Message.conversation_id == conversation_id, Message.direction == "inbound"
            )
        )
        inbound_count = count_result.scalar_one()

        recent_result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(3)
        )
        recent_messages = [m.text for m in reversed(recent_result.scalars().all())]

        classification = tools.classify_text(latest_message.text, is_first_message=inbound_count == 1)
        flags = tools.compute_routing_flags(classification)

        # Deterministic today (see tools.py docstring for why). Swapping in a
        # live provider later means building `messages` from
        # `prompts.render_classification_prompt(...)` instead of this
        # pre-built JSON, and parsing `result.text` as the classification
        # instead of trusting the local dict - everything else here is
        # unchanged.
        with timed() as t:
            llm_result = await llm_service.complete(
                db,
                market_id=conversation.market_id,
                agent_name=AGENT_NAME,
                conversation_id=conversation_id,
                messages=[LLMMessage(role="user", content=json.dumps(classification))],
                tier="classification",
            )

        conversation.latest_intent = classification["intent"]
        conversation.latest_sentiment = classification["sentiment"]
        conversation.latest_urgency = tools.latest_urgency_label(flags)
        await db.flush()

        output = {**classification, **flags}
        await log_action(
            db,
            market_id=conversation.market_id,
            conversation_id=conversation_id,
            agent_name=AGENT_NAME,
            action_type="classify",
            input_json={
                "message_id": str(latest_message.id),
                "text": latest_message.text,
                "recent_messages": recent_messages,
            },
            output_json=output,
            model_name=llm_result.model_name,
            provider=llm_result.provider,
            tokens_in=llm_result.tokens_in,
            tokens_out=llm_result.tokens_out,
            estimated_cost=llm_result.estimated_cost,
            latency_ms=t.ms,
        )

        return output


classifier_agent = ClassifierAgent()
