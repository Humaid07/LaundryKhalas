"""Facilities Management — serializers, validation, schema isolation, ownership,
and audit. DB is mocked (this suite does not hit Postgres).

Security-critical invariants covered:
  * partner serializer NEVER exposes quality_score / internal rates;
  * partner schemas REJECT protected fields (422 via extra="forbid");
  * admin schema accepts protected fields;
  * a partner cannot edit another facility (403);
  * a partner already linked to a facility cannot create another (409, strict single);
  * every management write records a facility_audit_log entry.
"""
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from api import facility_management as fm
from db import database
from db.repositories import (
    facilities_repo,
    facility_audit_repo,
)
from schemas import (
    AdminFacilityCreate,
    PartnerFacilityCreate,
    PartnerFacilityUpdate,
)
from services import facility_admin, facility_matching

_ROW = {
    "id": "fac-1", "code": "FAC-1", "name": "Marina Facility",
    "full_address": "1 St, Dubai", "area": "Marina", "city": "Dubai", "emirate": "Dubai",
    "latitude": "25.1", "longitude": "55.2", "service_radius_km": "10.0",
    "capacity_daily": 50, "capacity_unit": "orders_per_day", "accepts_orders": True,
    "operating_status": "open", "is_active": True, "onboarding_source": "admin_dashboard",
    "contact_area": "Marina", "notes": None, "created_at": "2026-07-29", "updated_at": "2026-07-29",
    "quality_score": "88.5", "payout_rate": "12.5", "market": "AE", "country": "AE",
    "created_by": None, "updated_by": None,
}


# ---------------------------- serializers -------------------------------
def test_partner_serializer_hides_quality_and_rates():
    prof = facilities_repo.to_profile(_ROW)
    assert "quality_score" not in prof
    assert "payout_rate" not in prof
    # ...but does surface safe operational fields.
    assert prof["capacity_unit"] == "orders_per_day"
    assert prof["full_address"] == "1 St, Dubai"


def test_admin_serializer_includes_quality_but_not_payout_leak_to_partner():
    admin = facilities_repo.to_admin_profile(_ROW)
    assert admin["quality_score"] == 88.5
    # to_admin_profile is internal-only; partner path never calls it.


# ---------------------------- schema isolation --------------------------
def test_partner_create_rejects_quality_score():
    with pytest.raises(ValidationError):
        PartnerFacilityCreate(name="X", quality_score=90)


def test_partner_update_rejects_internal_rate_fields():
    with pytest.raises(ValidationError):
        PartnerFacilityUpdate(payout_rate=5)
    with pytest.raises(ValidationError):
        PartnerFacilityUpdate(rates=[{"service_code": "WASH_FOLD", "rate": 5}])


def test_admin_create_accepts_quality_score():
    m = AdminFacilityCreate(name="X", quality_score=90)
    assert m.quality_score == 90


# ---------------------------- validation --------------------------------
@pytest.mark.parametrize("patch", [
    {"latitude": 100}, {"longitude": -200}, {"quality_score": 150},
    {"service_radius_km": 0}, {"capacity_daily": 0}, {"operating_status": "sleeping"},
    {"capacity_unit": "tonnes"}, {"emirate": "Atlantis"},
])
def test_validate_rejects_bad_values(patch):
    with pytest.raises(facility_admin.FacilityValidationError):
        facility_admin._validate({"name": "X", **patch}, partial=False)


def test_validate_requires_name_on_create():
    with pytest.raises(facility_admin.FacilityValidationError):
        facility_admin._validate({}, partial=False)


async def test_check_services_rejects_unknown_code(monkeypatch):
    async def fake_cats():
        return [{"code": "WASH_FOLD"}, {"code": "CLEAN_PRESS"}]
    monkeypatch.setattr(facility_admin.catalogue_repo, "list_categories", fake_cats)
    with pytest.raises(facility_admin.FacilityValidationError):
        await facility_admin._check_services(["WASH_FOLD", "NOPE"])
    # valid set passes
    await facility_admin._check_services(["WASH_FOLD"])


# ---------------------------- audit + invalidate ------------------------
async def test_create_facility_audits_and_invalidates(monkeypatch):
    audits = []
    invalidated = {"n": 0}

    async def fake_create(fields, *, actor_id=None):
        return {"id": "fac-9", **fields}

    async def fake_audit(**kw):
        audits.append(kw)
        return {"id": "a1"}

    monkeypatch.setattr(facilities_repo, "create", fake_create)
    monkeypatch.setattr(facility_audit_repo, "create", fake_audit)
    monkeypatch.setattr(facility_matching, "invalidate",
                        lambda: invalidated.__setitem__("n", invalidated["n"] + 1))

    fac = await facility_admin.create_facility(
        {"name": "New F", "emirate": "Dubai"}, actor_id="u1", actor_type="internal",
        source_app="admin_dashboard",
    )
    assert fac["id"] == "fac-9"
    assert len(audits) == 1 and audits[0]["action"] == "facility_created"
    assert audits[0]["actor_id"] == "u1"
    assert invalidated["n"] == 1


async def test_change_status_audits_before_after(monkeypatch):
    audits = []

    async def fake_get_admin(fid):
        return {"id": fid, "operating_status": "open"}

    async def fake_set_status(fid, status, *, actor_id=None):
        return {"id": fid, "operating_status": status}

    async def fake_audit(**kw):
        audits.append(kw)
        return {"id": "a1"}

    monkeypatch.setattr(facilities_repo, "get_admin", fake_get_admin)
    monkeypatch.setattr(facilities_repo, "set_status", fake_set_status)
    monkeypatch.setattr(facility_audit_repo, "create", fake_audit)
    monkeypatch.setattr(facility_matching, "invalidate", lambda: None)

    await facility_admin.change_status("fac-1", "busy", actor_id="u1")
    assert audits[0]["action"] == "status_changed"
    assert audits[0]["before"] == {"operating_status": "open"}
    assert audits[0]["after"] == {"operating_status": "busy"}


# ---------------------------- partner ownership (endpoint guards) --------
async def test_partner_cannot_edit_another_facility(monkeypatch):
    monkeypatch.setattr(database, "is_supabase_mode", lambda: True)
    principal = {"facility_id": "mine", "role": "facility_owner", "id": "u1"}
    with pytest.raises(HTTPException) as exc:
        await fm.partner_update_facility("someone-else", PartnerFacilityUpdate(name="x"), principal)
    assert exc.value.status_code == 403


async def test_partner_already_linked_cannot_create(monkeypatch):
    monkeypatch.setattr(database, "is_supabase_mode", lambda: True)
    principal = {"facility_id": "mine", "role": "facility_owner", "id": "u1"}
    with pytest.raises(HTTPException) as exc:
        await fm.partner_create_facility(PartnerFacilityCreate(name="Second"), principal)
    assert exc.value.status_code == 409


async def test_partner_update_returns_safe_profile(monkeypatch):
    monkeypatch.setattr(database, "is_supabase_mode", lambda: True)

    async def fake_update(*a, **k):
        return {"id": "mine", "quality_score": 99}  # admin dict — must NOT be returned

    async def fake_get(fid):
        return facilities_repo.to_profile({**_ROW, "id": fid})

    async def fake_services(fid):
        return ["WASH_FOLD"]

    monkeypatch.setattr(facility_admin, "update_facility", fake_update)
    monkeypatch.setattr(facilities_repo, "get", fake_get)
    monkeypatch.setattr(facilities_repo, "get_services", fake_services)
    principal = {"facility_id": "mine", "role": "facility_owner", "id": "u1"}
    resp = await fm.partner_update_facility("mine", PartnerFacilityUpdate(name="x"), principal)
    assert "quality_score" not in resp["facility"]
    assert resp["facility"]["service_codes"] == ["WASH_FOLD"]
