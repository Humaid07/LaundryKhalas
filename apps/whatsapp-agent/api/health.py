"""Health endpoints. Report DB mode/connectivity and the AI integration status
without exposing any secrets. Never performs a paid Anthropic call.
"""
from fastapi import APIRouter

from db import database
from settings import get_settings

router = APIRouter(tags=["health"])


@router.get("/health/db")
async def health_db():
    return await database.db_health()


@router.get("/health/ai")
async def health_ai():
    """Readiness of the AI provider — provider, enabled, whether a key is
    configured, and the resolved model. NEVER returns the key itself and does
    NOT make a billed API request (use scripts/test_anthropic.py for that)."""
    return get_settings().ai_status
