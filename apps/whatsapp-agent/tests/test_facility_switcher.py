"""Dev-only facility switcher: the guard honors an X-Facility-Id header ONLY when
auth is off (dev), and the /switchable list endpoint self-disables in production.

Security invariant under test: when REQUIRE_AUTH is on, a client-supplied
facility (header) is ignored — a facility user stays locked to their own
facility. See docs/superpowers/specs/2026-08-07-facility-switcher-dev-design.md
"""
import pytest
from starlette.requests import Request

from api import deps, facility
from db import database


class _Settings:
    def __init__(self, require_auth: bool, facility_dev_id: str = ""):
        self.require_auth = require_auth
        self.facility_dev_id = facility_dev_id


def _request(headers: dict | None = None) -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    return Request({"type": "http", "method": "GET", "path": "/",
                    "query_string": b"", "headers": raw})


# --- require_facility_scope: dev branch honors a valid override --------------
@pytest.mark.asyncio
async def test_dev_honors_valid_x_facility_id_header(monkeypatch):
    monkeypatch.setattr(deps, "get_settings", lambda: _Settings(require_auth=False))
    monkeypatch.setattr(deps, "current_user", _async(None))
    monkeypatch.setattr(deps, "_dev_facility_id", _async("DEFAULT-FAC"))
    monkeypatch.setattr(database, "fetchval", _async(True))  # facility exists

    principal = await deps.require_facility_scope(_request({"X-Facility-Id": "FAC-XYZ"}))

    assert principal["facility_id"] == "FAC-XYZ"


@pytest.mark.asyncio
async def test_dev_ignores_unknown_x_facility_id_header(monkeypatch):
    monkeypatch.setattr(deps, "get_settings", lambda: _Settings(require_auth=False))
    monkeypatch.setattr(deps, "current_user", _async(None))
    monkeypatch.setattr(deps, "_dev_facility_id", _async("DEFAULT-FAC"))
    monkeypatch.setattr(database, "fetchval", _async(False))  # facility does NOT exist

    principal = await deps.require_facility_scope(_request({"X-Facility-Id": "BOGUS"}))

    assert principal["facility_id"] == "DEFAULT-FAC"  # fell back to the default


@pytest.mark.asyncio
async def test_dev_no_header_uses_default(monkeypatch):
    monkeypatch.setattr(deps, "get_settings", lambda: _Settings(require_auth=False))
    monkeypatch.setattr(deps, "current_user", _async(None))
    monkeypatch.setattr(deps, "_dev_facility_id", _async("DEFAULT-FAC"))

    principal = await deps.require_facility_scope(_request())

    assert principal["facility_id"] == "DEFAULT-FAC"


# --- require_facility_scope: auth ON ignores the header (security) -----------
@pytest.mark.asyncio
async def test_auth_on_ignores_x_facility_id_header(monkeypatch):
    monkeypatch.setattr(deps, "get_settings", lambda: _Settings(require_auth=True))
    facility_user = {"id": "u1", "email": "f@x", "role": "facility_owner",
                     "is_active": True, "facility_id": "OWN-FAC"}
    monkeypatch.setattr(deps, "current_user", _async(facility_user))

    principal = await deps.require_facility_scope(_request({"X-Facility-Id": "OTHER-FAC"}))

    assert principal["facility_id"] == "OWN-FAC"  # header ignored, locked to own


# --- /switchable list endpoint ----------------------------------------------
@pytest.mark.asyncio
async def test_switchable_returns_facilities_in_dev(monkeypatch):
    monkeypatch.setattr(facility, "get_settings", lambda: _Settings(require_auth=False))
    monkeypatch.setattr(database, "is_supabase_mode", lambda: True)
    rows = [{"id": "a", "name": "Abu Dhabi Central", "city": "Abu Dhabi"},
            {"id": "b", "name": "TEST Barsha One", "city": "Dubai"}]
    monkeypatch.setattr(database, "fetch", _async(rows))

    out = await facility.facility_switchable(principal={"facility_id": "a"})

    assert [f["id"] for f in out] == ["a", "b"]
    assert out[1]["city"] == "Dubai"


@pytest.mark.asyncio
async def test_switchable_empty_when_auth_on(monkeypatch):
    monkeypatch.setattr(facility, "get_settings", lambda: _Settings(require_auth=True))
    monkeypatch.setattr(database, "is_supabase_mode", lambda: True)

    out = await facility.facility_switchable(principal={"facility_id": "a"})

    assert out == []


# --- helper -----------------------------------------------------------------
def _async(value):
    async def _f(*args, **kwargs):
        return value
    return _f
