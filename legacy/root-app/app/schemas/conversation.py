import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.message import MessageRead


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    market_id: uuid.UUID
    customer_id: uuid.UUID
    channel: str
    external_thread_id: str | None
    status: str
    assigned_to_user_id: str | None
    manual_takeover: bool
    latest_intent: str | None
    latest_sentiment: str | None
    latest_urgency: str | None
    created_at: datetime
    updated_at: datetime


class ConversationDetail(ConversationRead):
    messages: list[MessageRead] = []


class ManualTakeoverRequest(BaseModel):
    taken_over_by: str
