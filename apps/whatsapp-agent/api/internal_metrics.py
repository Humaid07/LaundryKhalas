"""Internal (ops) quality-metrics report.

Deterministic conversion / repeat / escalation rollups for the ops dashboard.
Guarded by ``deps.require_ops`` at include time. Read-only; returns an all-zero
report outside supabase mode.
"""
from __future__ import annotations

from fastapi import APIRouter

from db.repositories import metrics_repo

router = APIRouter(prefix="/api/internal/metrics", tags=["metrics"])


@router.get("/quality")
async def quality():
    return await metrics_repo.quality_report()
