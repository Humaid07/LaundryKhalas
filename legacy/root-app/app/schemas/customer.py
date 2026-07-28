import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CustomerAddressRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    label: str | None
    address_text: str
    area: str | None
    city: str | None
    is_default: bool


class CustomerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    market_id: uuid.UUID
    phone_number: str
    name: str | None
    email: str | None
    preferred_language: str
    created_at: datetime
