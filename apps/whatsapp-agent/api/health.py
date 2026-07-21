"""Database health endpoint. Reports the active DB mode (sqlite vs the dev/test
Supabase Postgres) and connectivity, without exposing any secrets.
"""
from fastapi import APIRouter

from db import database

router = APIRouter(tags=["health"])


@router.get("/health/db")
async def health_db():
    return await database.db_health()
