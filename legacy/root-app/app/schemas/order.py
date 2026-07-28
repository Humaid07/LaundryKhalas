import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    market_id: uuid.UUID
    customer_id: uuid.UUID
    facility_id: uuid.UUID | None
    status: str
    service_type: str
    items_json: dict
    address_id: uuid.UUID | None
    pickup_window_start: datetime | None
    pickup_window_end: datetime | None
    delivery_window_start: datetime | None
    delivery_window_end: datetime | None
    estimated_total: float | None
    payment_status: str
    source_channel: str
    created_at: datetime
    updated_at: datetime


class OrderEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order_id: uuid.UUID
    event_type: str
    from_status: str | None
    to_status: str | None
    actor_type: str
    actor_id: str | None
    metadata_json: dict
    created_at: datetime
