import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.channels.mock_whatsapp import mock_whatsapp_adapter
from app.models.human_approval import HumanApproval
from app.services.audit import log_action


class ApprovalNotPending(Exception):
    pass


async def create_approval_request(
    db: AsyncSession,
    *,
    market_id: uuid.UUID,
    requested_by_agent: str,
    action_type: str,
    proposed_payload: dict,
    reason: str | None = None,
    conversation_id: uuid.UUID | None = None,
    order_id: uuid.UUID | None = None,
) -> HumanApproval:
    approval = HumanApproval(
        market_id=market_id,
        conversation_id=conversation_id,
        order_id=order_id,
        requested_by_agent=requested_by_agent,
        action_type=action_type,
        reason=reason,
        proposed_payload_json=proposed_payload,
        status="pending",
    )
    db.add(approval)
    await db.flush()

    await log_action(
        db,
        market_id=market_id,
        conversation_id=conversation_id,
        order_id=order_id,
        agent_name=requested_by_agent,
        action_type="create_approval_request",
        input_json={"action_type": action_type, "reason": reason},
        output_json={"approval_id": str(approval.id)},
    )
    return approval


async def get_approval(db: AsyncSession, approval_id: uuid.UUID) -> HumanApproval | None:
    result = await db.execute(select(HumanApproval).where(HumanApproval.id == approval_id))
    return result.scalar_one_or_none()


async def list_approvals(
    db: AsyncSession, *, status: str | None = None
) -> list[HumanApproval]:
    query = select(HumanApproval).order_by(HumanApproval.created_at.desc())
    if status:
        query = query.where(HumanApproval.status == status)
    result = await db.execute(query)
    return list(result.scalars().all())


async def approve(
    db: AsyncSession, *, approval: HumanApproval, approved_by: str, decision_note: str | None = None
) -> HumanApproval:
    if approval.status != "pending":
        raise ApprovalNotPending(f"Approval {approval.id} is not pending (status={approval.status}).")

    approval.status = "approved"
    approval.approved_by = approved_by
    approval.decision_note = decision_note
    approval.decided_at = datetime.now(timezone.utc)
    await db.flush()

    output: dict = {}
    if approval.action_type == "send_customer_reply" and approval.conversation_id:
        text = approval.proposed_payload_json.get("text", "")
        result = await mock_whatsapp_adapter.send_outbound(
            db, conversation_id=str(approval.conversation_id), message=text
        )
        output = {"message_id": result.message_id, "status": result.status}

    await log_action(
        db,
        market_id=approval.market_id,
        conversation_id=approval.conversation_id,
        order_id=approval.order_id,
        agent_name="admin",
        action_type="approve_action",
        input_json={"approval_id": str(approval.id), "approved_by": approved_by},
        output_json=output,
    )
    return approval


async def reject(
    db: AsyncSession, *, approval: HumanApproval, rejected_by: str, decision_note: str | None = None
) -> HumanApproval:
    if approval.status != "pending":
        raise ApprovalNotPending(f"Approval {approval.id} is not pending (status={approval.status}).")

    approval.status = "rejected"
    approval.rejected_by = rejected_by
    approval.decision_note = decision_note
    approval.decided_at = datetime.now(timezone.utc)
    await db.flush()

    await log_action(
        db,
        market_id=approval.market_id,
        conversation_id=approval.conversation_id,
        order_id=approval.order_id,
        agent_name="admin",
        action_type="reject_action",
        input_json={"approval_id": str(approval.id), "rejected_by": rejected_by},
        output_json={},
    )
    return approval
