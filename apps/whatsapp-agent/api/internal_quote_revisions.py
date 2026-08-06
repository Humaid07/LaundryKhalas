"""Internal (ops) review of facility revised quotes.

Operations reviews a facility's proposed fee; the BACKEND computes the
customer-facing price from the margin rule (services/quote_revision), the customer
approves, and only then does the affected work resume (the blocking issue is
resolved). The facility fee + margin are internal; the customer flow sees only the
computed customer price. Guarded by ``deps.require_ops`` at include time.
"""
from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException

from db import database
from db.repositories import (
    facility_issues_repo,
    facility_quote_revisions_repo,
    order_events_repo,
)
from services import quote_revision as quote_revision_svc

router = APIRouter(prefix="/api/internal/quote-revisions", tags=["quote-revisions"])


def _require_supabase_write():
    if not database.is_supabase_mode():
        raise HTTPException(
            status_code=503,
            detail="Quote revisions require DATABASE_MODE=supabase (dev/test Supabase project).",
        )


@router.get("")
async def list_all(status: str | None = None):
    if not database.is_supabase_mode():
        return []
    return await facility_quote_revisions_repo.list_for(facility_id=None, status=status)


@router.get("/{revision_id}")
async def get_revision(revision_id: str):
    if not database.is_supabase_mode():
        raise HTTPException(status_code=404, detail="Revision not found.")
    rev = await facility_quote_revisions_repo.get(revision_id)
    if rev is None:
        raise HTTPException(status_code=404, detail="Revision not found.")
    return rev


async def _resolve_linked_issue(rev: dict, note: str) -> None:
    issue_id = rev.get("facility_issue_id")
    if issue_id:
        await facility_issues_repo.set_status(issue_id, "resolved")
    if rev.get("order_id"):
        await order_events_repo.create(
            order_uuid=rev["order_id"], event_type="facility_issue_resolved",
            actor_type="operations", actor_name="LaundryKhalas Team", notes=note,
            metadata={"revision_id": rev["id"]},
        )


@router.post("/{revision_id}/review")
async def review_revision(revision_id: str, body: dict = Body(...)):
    """Operations reviews the revised fee. ``decision``: 'approved' → compute the
    customer price (margin rule from the body or the default) and move to
    customer_pending; 'rejected' → reject and unblock the order."""
    _require_supabase_write()
    rev = await facility_quote_revisions_repo.get(revision_id)
    if rev is None:
        raise HTTPException(status_code=404, detail="Revision not found.")
    decision = (body or {}).get("decision")
    reviewer = (body or {}).get("reviewed_by") or "LaundryKhalas Team"

    if decision == "approved":
        if not quote_revision_svc.can_transition(rev["status"], "customer_pending"):
            raise HTTPException(status_code=409, detail=f"Cannot approve from '{rev['status']}'.")
        margin_rule = None
        if (body or {}).get("margin_value") is not None:
            margin_rule = {"margin_type": (body or {}).get("margin_type", "percentage"),
                           "margin_value": (body or {}).get("margin_value")}
        customer_price = quote_revision_svc.compute_customer_price(rev["facility_fee"], margin_rule)
        updated = await facility_quote_revisions_repo.set_review(
            revision_id, status="customer_pending", customer_price=customer_price, reviewed_by=reviewer)
        await order_events_repo.create(
            order_uuid=rev["order_id"], event_type="quote_revision_approved_by_ops",
            actor_type="operations", actor_name=reviewer,
            notes="Revised quote approved; awaiting customer approval.",
            metadata={"revision_id": revision_id},
        )
        # Proactively push the facility-confirmed price to the customer on WhatsApp
        # (best-effort, gated + idempotent; never breaks the ops action).
        from services import quote_outbound
        push = await quote_outbound.send_customer_quote(rev["order_id"], order_ref=rev.get("order_ref"))
        return {**(updated or {}), "customer_push": push}

    if decision == "rejected":
        if not quote_revision_svc.can_transition(rev["status"], "ops_rejected"):
            raise HTTPException(status_code=409, detail=f"Cannot reject from '{rev['status']}'.")
        updated = await facility_quote_revisions_repo.set_review(
            revision_id, status="ops_rejected", reviewed_by=reviewer)
        await _resolve_linked_issue(rev, "Revised quote rejected by operations.")
        return updated

    raise HTTPException(status_code=400, detail="decision must be 'approved' or 'rejected'.")


@router.post("/{revision_id}/customer-decision")
async def customer_decision(revision_id: str, body: dict = Body(...)):
    """Record the customer's decision on the (ops-approved) revised price. On
    approval the affected work resumes — the blocking issue is resolved. The
    customer only ever sees ``customer_price``; the facility fee is never exposed."""
    _require_supabase_write()
    rev = await facility_quote_revisions_repo.get(revision_id)
    if rev is None:
        raise HTTPException(status_code=404, detail="Revision not found.")
    decision = (body or {}).get("decision")
    target = {"approved": "customer_approved", "rejected": "customer_rejected"}.get(decision)
    if target is None:
        raise HTTPException(status_code=400, detail="decision must be 'approved' or 'rejected'.")
    if not quote_revision_svc.can_transition(rev["status"], target):
        raise HTTPException(status_code=409, detail=f"Cannot record decision from '{rev['status']}'.")
    updated = await facility_quote_revisions_repo.set_customer_decision(revision_id, status=target)
    await _resolve_linked_issue(
        rev, f"Customer {'approved' if decision == 'approved' else 'declined'} the revised price.")
    return updated
