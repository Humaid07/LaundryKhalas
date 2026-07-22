"""Support-ticket API. Supabase-backed in dev/test mode.

Tickets are the durable work items raised alongside an agent_flag when a
conversation needs human handling. Empty list in local SQLite mode.
"""
from fastapi import APIRouter

from db import database
from db.repositories import tickets_repo

router = APIRouter(prefix="/api/tickets", tags=["tickets"])


@router.get("")
async def list_tickets(status: str | None = None):
    if not database.is_supabase_mode():
        return []
    return await tickets_repo.list_tickets(status=status)
