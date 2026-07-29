"""Partner-facing Facilities Management API (facility portal).

A partner manages their OWN facility only. Ownership is resolved server-side from
the authenticated principal (``require_facility_scope`` → the caller's facility_id),
never from a client-supplied id. Protected fields (quality_score + internal rates)
are excluded from the PartnerFacility* schemas and rejected (422) via extra="forbid"
— they are never accepted, returned, or serialized on the partner side (CLAUDE.md §7).

Strict single-facility ownership: a facility user is bound to exactly one facility.
Create is allowed only for a not-yet-linked account (self-onboarding) and links the
new facility to the user; an already-linked account gets 409 and edits instead.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api import deps
from api.facility import _fid, _require_manage, _require_supabase_write
from db import database
from db.repositories import facilities_repo
from schemas import PartnerFacilityCreate, PartnerFacilityUpdate, FacilityStatusUpdate
from services import facility_admin

router = APIRouter(prefix="/api/facility", tags=["facility-management"])


@router.get("/facilities")
async def partner_list_facilities(principal: dict = Depends(deps.require_facility_scope)):
    """The partner's own facility (strict single ownership → 0 or 1)."""
    if not database.is_supabase_mode():
        return {"facilities": []}
    fid = _fid(principal)
    profile = await facilities_repo.get(fid)
    if profile is None:
        return {"facilities": []}
    profile["service_codes"] = await facilities_repo.get_services(fid)
    return {"facilities": [profile]}


@router.post("/facilities")
async def partner_create_facility(
    body: PartnerFacilityCreate,
    principal: dict = Depends(deps.require_roles("facility_owner", "facility_manager", "admin")),
):
    """Self-onboard the partner's first facility. 409 if already linked (strict
    single ownership). onboarding_source is forced to partner_portal — the partner
    never sets it, and never sets quality_score/rates (omitted from the schema)."""
    _require_supabase_write()
    user_id = (principal or {}).get("id")
    existing = (principal or {}).get("facility_id")
    if not existing and user_id:
        existing = await database.fetchval(
            "select facility_id::text from users where id = $1", user_id
        )
    if existing:
        raise HTTPException(
            status_code=409,
            detail="Your account is already linked to a facility. You can edit it, not add another.",
        )
    fields = body.model_dump(exclude_unset=True)
    fields["onboarding_source"] = "partner_portal"
    try:
        facility = await facility_admin.create_facility(
            fields, actor_id=user_id, actor_type="partner", source_app="partner_portal",
        )
    except facility_admin.FacilityValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    # Link the new facility to the authenticated partner (strict single ownership).
    if facility and user_id:
        await database.execute(
            "update users set facility_id = $2 where id = $1", user_id, facility["id"]
        )
    # Return the PARTNER-SAFE serializer (never the admin one).
    return {"facility": await facilities_repo.get(facility["id"]) if facility else None}


@router.patch("/facilities/{facility_id}")
async def partner_update_facility(
    facility_id: str, body: PartnerFacilityUpdate,
    principal: dict = Depends(deps.require_facility_scope),
):
    _require_supabase_write()
    fid = _fid(principal)
    if facility_id != fid:
        raise HTTPException(status_code=403, detail="You can only edit your own facility.")
    _require_manage(principal)
    try:
        await facility_admin.update_facility(
            fid, body.model_dump(exclude_unset=True),
            actor_id=(principal or {}).get("id"), actor_type="partner",
            source_app="partner_portal",
        )
    except facility_admin.FacilityValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    # Partner-safe response — quality_score/rates are never included.
    profile = await facilities_repo.get(fid)
    if profile:
        profile["service_codes"] = await facilities_repo.get_services(fid)
    return {"facility": profile}


@router.patch("/facilities/{facility_id}/status")
async def partner_update_status(
    facility_id: str, body: FacilityStatusUpdate,
    principal: dict = Depends(deps.require_facility_scope),
):
    _require_supabase_write()
    fid = _fid(principal)
    if facility_id != fid:
        raise HTTPException(status_code=403, detail="You can only edit your own facility.")
    _require_manage(principal)
    try:
        await facility_admin.change_status(
            fid, body.status, actor_id=(principal or {}).get("id"),
            actor_type="partner", source_app="partner_portal",
        )
    except facility_admin.FacilityValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"facility": await facilities_repo.get(fid)}
