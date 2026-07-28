import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_admin
from app.db.session import get_db
from app.models.conversation import Conversation
from app.schemas.conversation import ConversationDetail, ConversationRead, ManualTakeoverRequest
from app.services.audit import log_action

router = APIRouter(prefix="/admin/conversations", tags=["admin:conversations"])


@router.get("", response_model=list[ConversationRead], dependencies=[Depends(require_admin)])
async def list_conversations(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Conversation).order_by(Conversation.updated_at.desc()))
    return list(result.scalars().all())


@router.get(
    "/{conversation_id}", response_model=ConversationDetail, dependencies=[Depends(require_admin)]
)
async def get_conversation(conversation_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    await db.refresh(conversation, attribute_names=["messages"])
    return conversation


@router.post(
    "/{conversation_id}/manual-takeover",
    response_model=ConversationRead,
    dependencies=[Depends(require_admin)],
)
async def manual_takeover(
    conversation_id: uuid.UUID, payload: ManualTakeoverRequest, db: AsyncSession = Depends(get_db)
):
    conversation = await _get_or_404(db, conversation_id)
    conversation.manual_takeover = True
    conversation.assigned_to_user_id = payload.taken_over_by
    await db.flush()
    await log_action(
        db, market_id=conversation.market_id, conversation_id=conversation.id,
        agent_name="admin", action_type="manual_takeover",
        input_json={"taken_over_by": payload.taken_over_by}, output_json={},
    )
    await db.commit()
    await db.refresh(conversation)
    return conversation


@router.post(
    "/{conversation_id}/release-takeover",
    response_model=ConversationRead,
    dependencies=[Depends(require_admin)],
)
async def release_takeover(conversation_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    conversation = await _get_or_404(db, conversation_id)
    conversation.manual_takeover = False
    conversation.assigned_to_user_id = None
    await db.flush()
    await log_action(
        db, market_id=conversation.market_id, conversation_id=conversation.id,
        agent_name="admin", action_type="release_takeover", input_json={}, output_json={},
    )
    await db.commit()
    await db.refresh(conversation)
    return conversation


async def _get_or_404(db: AsyncSession, conversation_id: uuid.UUID) -> Conversation:
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conversation = result.scalar_one_or_none()
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation
