import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.classifier.agent import (
    ClassifierConversationNotFound,
    NoInboundMessageToClassify,
    classifier_agent,
)
from app.agents.whatsapp_operations.agent import (
    ConversationNotFound,
    ManualTakeoverActive,
    operations_happy_path_agent,
)
from app.core.security import require_admin
from app.db.session import get_db
from app.models.ai_action_log import AIActionLog
from app.models.market import Market
from app.schemas.market import MarketRead

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/markets", response_model=list[MarketRead], dependencies=[Depends(require_admin)])
async def list_markets(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Market).order_by(Market.code))
    return list(result.scalars().all())


@router.post("/conversations/{conversation_id}/classify", dependencies=[Depends(require_admin)])
async def classify_conversation(conversation_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    try:
        result = await classifier_agent.classify(db, conversation_id=conversation_id)
    except ClassifierConversationNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except NoInboundMessageToClassify as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    await db.commit()
    return result


@router.post("/conversations/{conversation_id}/run-agent", dependencies=[Depends(require_admin)])
async def run_agent(conversation_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    try:
        final_state = await operations_happy_path_agent.run(db, conversation_id=conversation_id)
    except ConversationNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ManualTakeoverActive as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    await db.commit()
    return {
        "decision": final_state.get("decision"),
        "approval_id": final_state.get("approval_id"),
        "order_id": final_state.get("order_id"),
        "draft_reply_text": final_state.get("draft_reply_text"),
    }


@router.get("/ai-action-logs", dependencies=[Depends(require_admin)])
async def list_ai_action_logs(
    conversation_id: uuid.UUID | None = None,
    order_id: uuid.UUID | None = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    query = select(AIActionLog).order_by(AIActionLog.created_at.desc()).limit(min(limit, 500))
    if conversation_id:
        query = query.where(AIActionLog.conversation_id == conversation_id)
    if order_id:
        query = query.where(AIActionLog.order_id == order_id)
    result = await db.execute(query)
    logs = result.scalars().all()
    return [
        {
            "id": str(log.id),
            "market_id": str(log.market_id),
            "conversation_id": str(log.conversation_id) if log.conversation_id else None,
            "order_id": str(log.order_id) if log.order_id else None,
            "agent_name": log.agent_name,
            "action_type": log.action_type,
            "tool_name": log.tool_name,
            "input_json": log.input_json,
            "output_json": log.output_json,
            "model_name": log.model_name,
            "provider": log.provider,
            "tokens_in": log.tokens_in,
            "tokens_out": log.tokens_out,
            "estimated_cost": float(log.estimated_cost),
            "latency_ms": log.latency_ms,
            "success": log.success,
            "error_message": log.error_message,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]
