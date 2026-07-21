"""Agent-flag (handoff/escalation) API. Supabase-backed in dev/test mode."""
from fastapi import APIRouter, HTTPException

from db import database
from db.repositories import flags_repo

router = APIRouter(prefix="/api/flags", tags=["flags"])


@router.get("")
async def list_flags(status: str | None = None):
    if not database.is_supabase_mode():
        return []
    return await flags_repo.list_flags(status=status)


@router.post("/{flag_id}/resolve")
async def resolve_flag(flag_id: str):
    if not database.is_supabase_mode():
        raise HTTPException(
            status_code=503,
            detail="Flags require DATABASE_MODE=supabase (dev/test Supabase project).",
        )
    flag = await flags_repo.resolve(flag_id)
    if flag is None:
        raise HTTPException(status_code=404, detail="Flag not found.")
    return flag
