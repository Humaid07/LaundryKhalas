import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.channels.mock_whatsapp import mock_whatsapp_adapter
from app.core.security import require_admin
from app.db.session import get_db
from app.models.conversation import Conversation
from app.models.message import Message
from app.schemas.message import ManualReplyCreate, MessageRead
from app.services.audit import log_action

router = APIRouter(prefix="/admin/conversations", tags=["admin:messages"])


@router.get(
    "/{conversation_id}/messages",
    response_model=list[MessageRead],
    dependencies=[Depends(require_admin)],
)
async def list_messages(conversation_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    return list(result.scalars().all())


@router.post(
    "/{conversation_id}/manual-reply",
    response_model=MessageRead,
    dependencies=[Depends(require_admin)],
)
async def manual_reply(
    conversation_id: uuid.UUID, payload: ManualReplyCreate, db: AsyncSession = Depends(get_db)
):
    conv_result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conversation = conv_result.scalar_one_or_none()
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    result = await mock_whatsapp_adapter.send_outbound(
        db, conversation_id=str(conversation_id), message=payload.text
    )

    msg_result = await db.execute(select(Message).where(Message.id == uuid.UUID(result.message_id)))
    message = msg_result.scalar_one()
    message.sender_type = "admin"
    await db.flush()

    await log_action(
        db, market_id=conversation.market_id, conversation_id=conversation_id,
        agent_name="admin", action_type="manual_reply",
        input_json={"text": payload.text}, output_json={"message_id": result.message_id},
    )
    await db.commit()
    await db.refresh(message)
    return message
