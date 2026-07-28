"""Operations Human-Intervention queue + takeover actions.

Backend-authoritative endpoints for the abuse/threat takeover workflow. The
queue read is PII-safe (masked phone + sanitized preview only). Actions are
gated by the ops role (router-level in main.py); releasing a SEVERE-threat
conversation to AI additionally requires an admin (supervisor).

Human dashboard replies keep using the existing POST
/api/conversations/{id}/human-message (stores + sends via Evolution) — the AI
stays paused throughout because the conversation is in 'human_takeover'.
"""
import structlog
from fastapi import APIRouter, HTTPException, Request

from api import deps
from db import database
from db.repositories import human_interventions_repo as hi_repo
from services import human_intervention as hint

logger = structlog.get_logger()

router = APIRouter(prefix="/api/human-intervention", tags=["human-intervention"])


def _require_supabase():
    if not database.is_supabase_mode():
        raise HTTPException(
            status_code=503,
            detail="Human intervention requires DATABASE_MODE=supabase (dev/test Supabase).")


async def _agent_ctx(request: Request) -> tuple[str, str | None, bool]:
    """(agent_id, agent_name, is_supervisor) from the authenticated user. In dev
    (auth off) falls back to a generic operator so the flow is usable."""
    user = await deps.current_user(request) or {}
    agent_id = user.get("email") or user.get("id") or "operator"
    return agent_id, user.get("email"), user.get("role") == "admin"


@router.get("/queue")
async def queue(status: str | None = None, reason: str | None = None,
                severity: str | None = None, assigned_agent_id: str | None = None,
                market: str | None = None):
    if not database.is_supabase_mode():
        return []
    return await hi_repo.list_queue(status=status, reason=reason, severity=severity,
                                    assigned_agent_id=assigned_agent_id, market=market)


@router.get("/metrics")
async def metrics():
    if not database.is_supabase_mode():
        return {}
    return await hi_repo.metrics()


@router.get("/{intervention_id}")
async def get_one(intervention_id: str):
    _require_supabase()
    row = await hi_repo.get(intervention_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Intervention not found.")
    return row


@router.post("/{intervention_id}/claim")
async def claim(intervention_id: str, request: Request):
    _require_supabase()
    agent_id, agent_name, _ = await _agent_ctx(request)
    try:
        return await hint.claim(intervention_id, agent_id=agent_id, agent_name=agent_name)
    except hint.InterventionError as exc:
        code = 409 if exc.code == "conflict" else (404 if exc.code == "not_found" else 400)
        raise HTTPException(status_code=code, detail=exc.message)


@router.post("/{intervention_id}/resolve")
async def resolve(intervention_id: str, request: Request):
    _require_supabase()
    agent_id, _, _ = await _agent_ctx(request)
    body = {}
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001 - body optional
        pass
    try:
        return await hint.resolve(intervention_id, agent_id=agent_id,
                                  resolution_reason=(body or {}).get("resolution_reason"),
                                  close=bool((body or {}).get("close")))
    except hint.InterventionError as exc:
        raise HTTPException(status_code=404 if exc.code == "not_found" else 400,
                            detail=exc.message)


@router.post("/{intervention_id}/release-to-ai")
async def release_to_ai(intervention_id: str, request: Request):
    _require_supabase()
    agent_id, _, is_supervisor = await _agent_ctx(request)
    try:
        return await hint.release_to_ai(intervention_id, agent_id=agent_id,
                                        is_supervisor=is_supervisor)
    except hint.InterventionError as exc:
        code = {"forbidden": 403, "not_found": 404}.get(exc.code, 400)
        raise HTTPException(status_code=code, detail=exc.message)
