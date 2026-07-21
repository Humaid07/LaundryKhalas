import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    direction: str
    sender_type: str
    text: str
    status: str
    created_at: datetime


class ManualReplyCreate(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class MockInboundMessage(BaseModel):
    market_code: str = Field(min_length=2, max_length=8)
    phone_number: str = Field(min_length=6, max_length=32)
    customer_name: str | None = None
    message: str = Field(min_length=1, max_length=4000)


class MockOutboundMessage(BaseModel):
    conversation_id: uuid.UUID
    message: str = Field(min_length=1, max_length=4000)


class MockInboundResponse(BaseModel):
    conversation_id: uuid.UUID
    message_id: uuid.UUID
    customer_id: uuid.UUID


class MockOutboundResponse(BaseModel):
    message_id: uuid.UUID
    status: str
