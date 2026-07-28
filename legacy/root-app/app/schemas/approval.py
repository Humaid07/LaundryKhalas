import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class HumanApprovalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    market_id: uuid.UUID
    conversation_id: uuid.UUID | None
    order_id: uuid.UUID | None
    requested_by_agent: str
    action_type: str
    reason: str | None
    proposed_payload_json: dict
    status: str
    approved_by: str | None
    rejected_by: str | None
    decision_note: str | None
    created_at: datetime
    decided_at: datetime | None


class ApprovalDecisionRequest(BaseModel):
    decided_by: str
    decision_note: str | None = None
