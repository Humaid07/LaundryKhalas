import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_admin
from app.db.session import get_db
from app.schemas.approval import ApprovalDecisionRequest, HumanApprovalRead
from app.services.approvals import (
    ApprovalNotPending,
    approve,
    get_approval,
    list_approvals,
    reject,
)

router = APIRouter(prefix="/admin/approvals", tags=["admin:approvals"])


@router.get("", response_model=list[HumanApprovalRead], dependencies=[Depends(require_admin)])
async def list_approvals_route(status: str | None = None, db: AsyncSession = Depends(get_db)):
    return await list_approvals(db, status=status)


@router.get(
    "/{approval_id}", response_model=HumanApprovalRead, dependencies=[Depends(require_admin)]
)
async def get_approval_route(approval_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    approval = await get_approval(db, approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    return approval


@router.post(
    "/{approval_id}/approve",
    response_model=HumanApprovalRead,
    dependencies=[Depends(require_admin)],
)
async def approve_route(
    approval_id: uuid.UUID, payload: ApprovalDecisionRequest, db: AsyncSession = Depends(get_db)
):
    approval = await get_approval(db, approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    try:
        approval = await approve(
            db, approval=approval, approved_by=payload.decided_by, decision_note=payload.decision_note
        )
    except ApprovalNotPending as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(approval)
    return approval


@router.post(
    "/{approval_id}/reject",
    response_model=HumanApprovalRead,
    dependencies=[Depends(require_admin)],
)
async def reject_route(
    approval_id: uuid.UUID, payload: ApprovalDecisionRequest, db: AsyncSession = Depends(get_db)
):
    approval = await get_approval(db, approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    try:
        approval = await reject(
            db, approval=approval, rejected_by=payload.decided_by, decision_note=payload.decision_note
        )
    except ApprovalNotPending as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(approval)
    return approval
