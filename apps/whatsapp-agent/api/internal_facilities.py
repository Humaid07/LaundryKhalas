"""Internal Facilities Management API (admin dashboard).

CRUD over the central ``facilities`` table for internal operators. Registered with
the ``require_ops`` guard (admin + operations); the internal-rate endpoints add an
extra ``require_admin`` guard because a facility's payable rate is admin-only. All
writes go through ``services.facility_admin`` so they are validated + audited +
invalidate the matching cache. Returns the INTERNAL serializer (includes
``quality_score``); the partner API (api/facility.py) uses the safe serializer.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api import deps
from db import database
from db.repositories import (
    catalogue_repo,
    facilities_repo,
    facility_audit_repo,
    facility_pricing_repo,
    facility_settings_repo,
)
from schemas import (
    AdminFacilityCreate,
    AdminFacilityUpdate,
    BankDetailsUpsert,
    FacilityRateUpsert,
    FacilityStatusUpdate,
)
from services import facility_admin, facility_bank, facility_overview
from services.facility_bank import BankValidationError

router = APIRouter(prefix="/api/internal/facilities", tags=["internal-facilities"])


def _require_supabase():
    if not database.is_supabase_mode():
        raise HTTPException(
            status_code=503,
            detail="Facilities Management requires DATABASE_MODE=supabase (dev/test Supabase project).",
        )


def _actor(principal: dict) -> str | None:
    return (principal or {}).get("id")


@router.get("")
async def list_facilities(
    search: str | None = None,
    status: str | None = None,
    emirate: str | None = None,
    service: str | None = None,
    principal: dict = Depends(deps.require_ops),
):
    if not database.is_supabase_mode():
        return {"facilities": [], "summary": {"total": 0, "open": 0, "busy": 0, "paused": 0, "closed": 0}}
    facilities = await facilities_repo.list_filtered(
        search=search, status=status, emirate=emirate, service_code=service
    )
    return {"facilities": facilities, "summary": await facilities_repo.status_counts()}


@router.get("/overview")
async def facilities_overview(
    city: str | None = None,
    emirate: str | None = None,
    status: str | None = None,
    service: str | None = None,
    days: int | None = 30,
    principal: dict = Depends(deps.require_ops),
):
    """Fleet-level facility performance + insights for the internal Overview page.

    Declared BEFORE ``/{facility_id}`` so the literal "overview" is not captured
    as a facility id. Returns an empty-but-shaped payload when not in Supabase
    mode (mirrors ``list_facilities``). ``days`` bounds the time-boxed metrics
    (completed orders, issues raised); pass ``days=0``/absent handling: 0 or
    negative → all-time.
    """
    empty = {
        "kpis": {
            "active_facilities": 0, "total_facilities": 0, "orders_completed": 0,
            "avg_completion_seconds": None, "avg_utilisation": None,
            "issues_raised": 0, "pending_actions": 0,
        },
        "most_active_facilities": [], "most_completed_facilities": [],
        "standout_by_city": [], "attention_facilities": [], "service_coverage": [],
        "filters_applied": {"city": city, "emirate": emirate, "status": status,
                            "service": service, "days": days},
    }
    if not database.is_supabase_mode():
        return empty
    filters = {
        "city": city, "emirate": emirate, "status": status, "service": service,
        "days": (days if (days and days > 0) else None),
    }
    return await facility_overview.build_overview(filters)


@router.get("/{facility_id}")
async def get_facility(facility_id: str, principal: dict = Depends(deps.require_ops)):
    _require_supabase()
    facility = await facilities_repo.get_admin(facility_id)
    if facility is None:
        raise HTTPException(status_code=404, detail="Facility not found.")
    facility["service_codes"] = await facilities_repo.get_services(facility_id)
    # Internal rates are ADMIN-ONLY and are fetched separately via GET /{id}/rates
    # (require_admin) — deliberately not included in this operations-visible bundle.
    return {
        "facility": facility,
        "services": facility["service_codes"],
        "timings": await facility_settings_repo.list_timings(facility_id),
        "audit": await facility_audit_repo.list_for_facility(facility_id),
    }


@router.post("")
async def create_facility(
    body: AdminFacilityCreate, principal: dict = Depends(deps.require_ops)
):
    _require_supabase()
    try:
        facility = await facility_admin.create_facility(
            body.model_dump(exclude_unset=True),
            actor_id=_actor(principal), actor_type="internal", source_app="admin_dashboard",
        )
    except facility_admin.FacilityValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return facility


@router.patch("/{facility_id}")
async def update_facility(
    facility_id: str, body: AdminFacilityUpdate,
    principal: dict = Depends(deps.require_ops),
):
    _require_supabase()
    try:
        facility = await facility_admin.update_facility(
            facility_id, body.model_dump(exclude_unset=True),
            actor_id=_actor(principal), actor_type="internal", source_app="admin_dashboard",
        )
    except facility_admin.FacilityValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if facility is None:
        raise HTTPException(status_code=404, detail="Facility not found.")
    return facility


@router.patch("/{facility_id}/status")
async def update_status(
    facility_id: str, body: FacilityStatusUpdate,
    principal: dict = Depends(deps.require_ops),
):
    _require_supabase()
    try:
        facility = await facility_admin.change_status(
            facility_id, body.status,
            actor_id=_actor(principal), actor_type="internal", source_app="admin_dashboard",
        )
    except facility_admin.FacilityValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if facility is None:
        raise HTTPException(status_code=404, detail="Facility not found.")
    return facility


# --- accepted services (category level, validated against the catalogue) ----
@router.get("/{facility_id}/services")
async def get_services(facility_id: str, principal: dict = Depends(deps.require_ops)):
    _require_supabase()
    return {
        "services": await facilities_repo.get_services(facility_id),
        "catalogue": await catalogue_repo.list_categories(),
    }


@router.put("/{facility_id}/services")
async def set_services(
    facility_id: str, body: dict, principal: dict = Depends(deps.require_ops)
):
    _require_supabase()
    codes = (body or {}).get("services", [])
    if not isinstance(codes, list):
        raise HTTPException(status_code=422, detail="'services' must be a list of category codes.")
    try:
        await facility_admin._check_services(codes)
    except facility_admin.FacilityValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    result = await facilities_repo.set_services(facility_id, codes)
    await facility_audit_repo.create(
        facility_id=facility_id, action="services_changed", actor_id=_actor(principal),
        actor_type="internal", source_app="admin_dashboard", after={"services": result},
    )
    return {"services": result}


# --- operating hours (structured, per weekday) ------------------------------
@router.get("/{facility_id}/timings")
async def get_timings(facility_id: str, principal: dict = Depends(deps.require_ops)):
    _require_supabase()
    return {"timings": await facility_settings_repo.list_timings(facility_id)}


@router.put("/{facility_id}/timings")
async def set_timings(
    facility_id: str, body: dict, principal: dict = Depends(deps.require_ops)
):
    _require_supabase()
    rows = body if isinstance(body, list) else (body or {}).get("timings", [])
    out = []
    for r in rows:
        dow = r.get("day_of_week")
        if dow is None:
            continue
        out.append(await facility_settings_repo.upsert_timing(
            facility_id, int(dow),
            opens_at=r.get("opens_at"), closes_at=r.get("closes_at"),
            receiving_start=r.get("receiving_start"), receiving_end=r.get("receiving_end"),
            handoff_start=r.get("handoff_start"), handoff_end=r.get("handoff_end"),
            same_day_cutoff=r.get("same_day_cutoff"),
            is_closed=r.get("is_closed", False), is_24h=r.get("is_24h", False),
        ))
    await facility_audit_repo.create(
        facility_id=facility_id, action="hours_changed", actor_id=_actor(principal),
        actor_type="internal", source_app="admin_dashboard",
    )
    return {"timings": out}


# --- internal rates (ADMIN ONLY) --------------------------------------------
@router.get("/{facility_id}/rates")
async def get_rates(facility_id: str, principal: dict = Depends(deps.require_admin)):
    _require_supabase()
    return {"rates": await facility_pricing_repo.list_rates(facility_id)}


@router.put("/{facility_id}/rates")
async def set_rate(
    facility_id: str, body: FacilityRateUpsert,
    principal: dict = Depends(deps.require_admin),
):
    _require_supabase()
    try:
        row = await facility_admin.set_rate(
            facility_id, body.service_code, body.rate, currency=body.currency,
            actor_id=_actor(principal), source_app="admin_dashboard",
        )
    except facility_admin.FacilityValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return row


@router.delete("/{facility_id}/rates/{service_code}")
async def delete_rate(
    facility_id: str, service_code: str, principal: dict = Depends(deps.require_admin)
):
    _require_supabase()
    ok = await facility_pricing_repo.delete_rate(facility_id, service_code)
    if not ok:
        raise HTTPException(status_code=404, detail="Rate not found.")
    await facility_audit_repo.create(
        facility_id=facility_id, action="rates_changed", actor_id=_actor(principal),
        actor_type="internal", source_app="admin_dashboard",
        after={"deleted_service_code": service_code},
    )
    return {"deleted": True}


# --- bank details -----------------------------------------------------------
# View (masked) is available to operations; creating/updating and the explicit
# full-value reveal are ADMIN-ONLY (banking is as sensitive as internal rates).
@router.get("/{facility_id}/bank-details")
async def get_bank_details(facility_id: str, principal: dict = Depends(deps.require_ops)):
    _require_supabase()
    return await facility_bank.get_masked(facility_id)


@router.put("/{facility_id}/bank-details")
async def put_bank_details(
    facility_id: str, body: BankDetailsUpsert,
    principal: dict = Depends(deps.require_admin),
):
    _require_supabase()
    if await facilities_repo.get_admin(facility_id) is None:
        raise HTTPException(status_code=404, detail="Facility not found.")
    try:
        return await facility_bank.upsert(
            facility_id, body.model_dump(exclude_unset=True),
            actor_id=_actor(principal), actor_type="internal",
            source_app="admin_dashboard",
        )
    except BankValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/{facility_id}/bank-details/reveal")
async def reveal_bank_details(
    facility_id: str, principal: dict = Depends(deps.require_admin)
):
    _require_supabase()
    revealed = await facility_bank.reveal(
        facility_id, actor_id=_actor(principal), actor_type="internal",
        source_app="admin_dashboard",
    )
    if revealed is None:
        raise HTTPException(status_code=404, detail="No bank details on file.")
    return revealed
