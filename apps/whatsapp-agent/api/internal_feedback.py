"""Internal (ops) customer-feedback review + global rule-change candidates.

Operations reviews captured feedback and decides: promote a customer-scoped item to
durable memory, queue a GLOBAL item as a versioned rule-change candidate, or reject.
Unreviewed global feedback NEVER changes production behaviour. Guarded by
``deps.require_ops`` at include time.
"""
from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException

from db import database
from db.repositories import customer_feedback_repo
from services import customer_feedback_service

router = APIRouter(prefix="/api/internal/feedback", tags=["feedback"])


def _require_supabase():
    if not database.is_supabase_mode():
        raise HTTPException(status_code=503, detail="Feedback review requires DATABASE_MODE=supabase.")


@router.get("")
async def list_feedback(status: str | None = None, limit: int = 100):
    if not database.is_supabase_mode():
        return []
    return await customer_feedback_repo.list_for_review(status=status, limit=min(int(limit), 200))


@router.post("/{feedback_id}/approve-memory")
async def approve_as_memory(feedback_id: str, body: dict = Body(...)):
    """Promote a customer-scoped feedback into durable customer memory."""
    _require_supabase()
    b = body or {}
    required = ("customer_id", "memory_type", "memory_key", "memory_value", "scope")
    if any(not b.get(k) for k in required):
        raise HTTPException(status_code=400, detail=f"Required: {', '.join(required)}.")
    return await customer_feedback_service.approve_feedback_as_customer_memory(
        feedback_id, customer_id=b["customer_id"], memory_type=b["memory_type"],
        memory_key=b["memory_key"], memory_value=b["memory_value"], scope=b["scope"],
        actor=b.get("actor"))


@router.post("/{feedback_id}/queue-global")
async def queue_global(feedback_id: str, body: dict = Body(...)):
    """Create a versioned GLOBAL rule-change candidate for authorized review."""
    _require_supabase()
    target = (body or {}).get("target")
    if not target:
        raise HTTPException(status_code=400, detail="A 'target' is required (system_prompt|service_rule|...).")
    cand = await customer_feedback_service.queue_global_feedback_review(
        feedback_id, target=target, proposed_change=(body or {}).get("proposed_change"))
    return cand or {}


@router.post("/{feedback_id}/reject")
async def reject(feedback_id: str, body: dict = Body(...)):
    _require_supabase()
    return await customer_feedback_service.reject_feedback(
        feedback_id, actor=(body or {}).get("actor"), duplicate=bool((body or {}).get("duplicate")))


@router.post("/candidates/{candidate_id}/approve")
async def approve_candidate(candidate_id: str, body: dict = Body(...)):
    """Approve a global rule-change candidate (still deployed via the normal
    versioned config process; this does not itself edit prompts/rules)."""
    _require_supabase()
    return await customer_feedback_service.approve_feedback_rule_change(
        candidate_id, approved_by=(body or {}).get("approved_by") or "Operations")
