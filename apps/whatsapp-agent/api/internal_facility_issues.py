"""Internal (ops) view of facility-raised issues.

The other side of api/facility.py issues: the LaundryKhalas operations team reads
issues across ALL facilities, sees internal-only notes, replies, and moves status.
Guarded by ``deps.require_ops`` at include time. Supabase-backed (mirrors flags/
tickets): reads return [] outside supabase mode, writes raise 503.
"""
from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException

from db import database
from db.repositories import (
    facility_issue_messages_repo,
    facility_issues_repo,
    order_events_repo,
    order_notes_repo,
)
from services import facility_notifications as facility_notify

router = APIRouter(prefix="/api/internal/facility-issues", tags=["facility-issues"])


def _require_supabase_write():
    if not database.is_supabase_mode():
        raise HTTPException(
            status_code=503,
            detail="Facility issues require DATABASE_MODE=supabase (dev/test Supabase project).",
        )


@router.get("")
async def list_all(status: str | None = None):
    if not database.is_supabase_mode():
        return []
    # facility_id=None → list across every facility (internal inbox).
    return await facility_issues_repo.list_issues(facility_id=None, status=status)


@router.get("/{issue_id}")
async def get_issue(issue_id: str):
    if not database.is_supabase_mode():
        raise HTTPException(status_code=404, detail="Issue not found.")
    issue = await facility_issues_repo.get(issue_id)
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found.")
    return issue


@router.get("/{issue_id}/messages")
async def get_messages(issue_id: str):
    if not database.is_supabase_mode():
        return []
    # Internal team sees ALL messages including internal-only notes.
    return await facility_issue_messages_repo.list_messages(issue_id, include_internal=True)


@router.post("/{issue_id}/reply")
async def reply(issue_id: str, body: dict = Body(...)):
    _require_supabase_write()
    message = (body or {}).get("message")
    if not message:
        raise HTTPException(status_code=400, detail="A 'message' is required.")
    issue = await facility_issues_repo.get(issue_id)
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found.")
    is_internal = bool((body or {}).get("is_internal", False))
    msg = await facility_issue_messages_repo.add_message(
        issue_id, "internal", message,
        sender_label=(body or {}).get("sender_label") or "LaundryKhalas Team",
        is_internal=is_internal,
    )
    # A public reply (not an internal note) puts the ball back on the facility and
    # notifies the facility's registered contacts (mock-first, never raises).
    if not is_internal:
        await facility_issues_repo.set_status(issue_id, "waiting_on_facility")
        await facility_notify.notify_internal_issue_reply(
            str(issue["facility_id"]), issue, message_id=str((msg or {}).get("id")),
        )
    return msg or {}


@router.post("/{issue_id}/clarification-answer")
async def clarification_answer(issue_id: str, body: dict = Body(...)):
    """Record the customer's answer to a facility clarification as an order
    AMENDMENT — linked to the affected item + this issue, never overwriting the
    original confirmed instruction. The amendment bumps the notes version, so the
    facility must re-acknowledge before continuing. The ball returns to the
    facility (status → waiting_on_facility)."""
    _require_supabase_write()
    answer = (body or {}).get("answer")
    if not answer:
        raise HTTPException(status_code=400, detail="An 'answer' is required.")
    issue = await facility_issues_repo.get(issue_id)
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found.")
    order_id = issue.get("order_id")
    if not order_id:
        raise HTTPException(status_code=422, detail="This issue is not linked to an order.")
    note = await order_notes_repo.add_amendment(
        str(order_id),
        category=(body or {}).get("category") or "ITEM_HANDLING",
        text=str(answer).strip(),
        order_item_id=(body or {}).get("order_item_id") or issue.get("order_item_id"),
        facility_issue_id=issue_id,
        source="OPERATIONS",
    )
    await order_events_repo.create(
        order_uuid=str(order_id), event_type="facility_clarification_answered",
        actor_type="operations", actor_name="LaundryKhalas Team",
        notes="Customer clarification recorded as an amendment.",
        metadata={"issue_id": issue_id, "note_id": str((note or {}).get("note_id"))},
    )
    await facility_issues_repo.set_status(issue_id, "waiting_on_facility")
    return {"amendment": note, "issue_status": "waiting_on_facility"}


@router.patch("/{issue_id}/status")
async def set_status(issue_id: str, body: dict = Body(...)):
    _require_supabase_write()
    status = (body or {}).get("status")
    if not status:
        raise HTTPException(status_code=400, detail="A 'status' is required.")
    updated = await facility_issues_repo.set_status(
        issue_id, status,
        assigned_internal_owner=(body or {}).get("assigned_internal_owner"),
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="Issue not found.")
    return updated
