"""Internal Ratings Management API (admin dashboard).

Authorized internal operators (admin + operations, via the router-level
``require_ops`` guard) rate facilities and drivers, edit evaluations, view full
history, and read internal summaries. The OFFICIAL overall score is computed on
the backend (services/ratings) — the client cannot submit an arbitrary overall.
Partner-facing reads live in api/facility.py and use the partner shaper.

Every write is audited (services/rating_service → facility_audit_log). Weighting
is config-controlled (config/rating_factors.json), never client-editable.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api import deps
from db import database
from db.repositories import facilities_repo, facility_drivers_repo
from schemas import EvaluationCreate, EvaluationUpdate
from services import ratings, rating_service
from services.ratings import RatingValidationError

router = APIRouter(prefix="/api/internal", tags=["internal-ratings"])


def _require_supabase():
    if not database.is_supabase_mode():
        raise HTTPException(
            status_code=503,
            detail="Ratings require DATABASE_MODE=supabase (dev/test Supabase project).",
        )


def _actor(principal: dict) -> str | None:
    return (principal or {}).get("id")


@router.get("/rating-factors")
async def rating_factors(principal: dict = Depends(deps.require_ops)):
    """Factor definitions + scale for the evaluation forms (config-driven)."""
    lo, hi = ratings.scale()
    return {
        "scale": {"min": lo, "max": hi},
        "facility_factors": ratings.factor_defs("facility"),
        "driver_factors": ratings.factor_defs("driver"),
    }


# ---------------------------------------------------------------- facilities
async def _require_facility(facility_id: str):
    if await facilities_repo.get_admin(facility_id) is None:
        raise HTTPException(status_code=404, detail="Facility not found.")


@router.get("/facilities/{facility_id}/drivers")
async def list_facility_drivers(facility_id: str, principal: dict = Depends(deps.require_ops)):
    """Real drivers for a facility (masked) so internal operators can rate them."""
    _require_supabase()
    await _require_facility(facility_id)
    return {"drivers": await facility_drivers_repo.list_drivers(facility_id)}


@router.get("/facilities/{facility_id}/rating")
async def facility_rating(facility_id: str, principal: dict = Depends(deps.require_ops)):
    _require_supabase()
    await _require_facility(facility_id)
    return await rating_service.facility_summary(facility_id)


@router.get("/facilities/{facility_id}/evaluations")
async def list_facility_evaluations(
    facility_id: str, status: str | None = None, limit: int = 50, offset: int = 0,
    principal: dict = Depends(deps.require_ops),
):
    _require_supabase()
    await _require_facility(facility_id)
    return await rating_service.list_facility_evaluations_internal(
        facility_id, status=status, limit=min(limit, 200), offset=offset)


@router.post("/facilities/{facility_id}/evaluations")
async def create_facility_evaluation(
    facility_id: str, body: EvaluationCreate, principal: dict = Depends(deps.require_ops),
):
    _require_supabase()
    await _require_facility(facility_id)
    try:
        return await rating_service.create_facility_evaluation(
            facility_id, body.model_dump(), actor_id=_actor(principal),
            source_app="admin_dashboard")
    except RatingValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.patch("/facilities/{facility_id}/evaluations/{evaluation_id}")
async def update_facility_evaluation(
    facility_id: str, evaluation_id: str, body: EvaluationUpdate,
    principal: dict = Depends(deps.require_ops),
):
    _require_supabase()
    try:
        row = await rating_service.update_facility_evaluation(
            facility_id, evaluation_id, body.model_dump(exclude_unset=True),
            actor_id=_actor(principal), source_app="admin_dashboard")
    except RatingValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if row is None:
        raise HTTPException(status_code=404, detail="Evaluation not found.")
    return row


# ---------------------------------------------------------------- drivers
async def _driver_facility_id(driver_id: str) -> str | None:
    """Resolve a driver's owning facility (internal is cross-facility)."""
    return await database.fetchval(
        "select facility_id::text from facility_drivers where id::text = $1", driver_id)


@router.get("/drivers/{driver_id}/rating")
async def driver_rating(driver_id: str, principal: dict = Depends(deps.require_ops)):
    _require_supabase()
    if await _driver_facility_id(driver_id) is None:
        raise HTTPException(status_code=404, detail="Driver not found.")
    return await rating_service.driver_summary(driver_id)


@router.get("/drivers/{driver_id}/evaluations")
async def list_driver_evaluations(
    driver_id: str, status: str | None = None, limit: int = 50, offset: int = 0,
    principal: dict = Depends(deps.require_ops),
):
    _require_supabase()
    if await _driver_facility_id(driver_id) is None:
        raise HTTPException(status_code=404, detail="Driver not found.")
    return await rating_service.list_driver_evaluations_internal(
        driver_id, status=status, limit=min(limit, 200), offset=offset)


@router.post("/drivers/{driver_id}/evaluations")
async def create_driver_evaluation(
    driver_id: str, body: EvaluationCreate, principal: dict = Depends(deps.require_ops),
):
    _require_supabase()
    facility_id = await _driver_facility_id(driver_id)
    if facility_id is None:
        raise HTTPException(status_code=404, detail="Driver not found.")
    try:
        return await rating_service.create_driver_evaluation(
            driver_id, body.model_dump(), facility_id=facility_id,
            actor_id=_actor(principal), source_app="admin_dashboard")
    except RatingValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.patch("/drivers/{driver_id}/evaluations/{evaluation_id}")
async def update_driver_evaluation(
    driver_id: str, evaluation_id: str, body: EvaluationUpdate,
    principal: dict = Depends(deps.require_ops),
):
    _require_supabase()
    try:
        row = await rating_service.update_driver_evaluation(
            driver_id, evaluation_id, body.model_dump(exclude_unset=True),
            actor_id=_actor(principal), source_app="admin_dashboard")
    except RatingValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if row is None:
        raise HTTPException(status_code=404, detail="Evaluation not found.")
    return row
