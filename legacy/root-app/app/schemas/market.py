import uuid

from pydantic import BaseModel, ConfigDict


class MarketRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    country: str
    currency: str
    is_active: bool
