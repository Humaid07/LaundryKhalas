"""Auth dependencies + RBAC guards for dashboard endpoints.

`require_roles(...)` is applied at router-include time in main.py. It is gated by
``REQUIRE_AUTH``: when off (local dev) it allows anonymous access as a synthetic
admin, so nothing breaks without logging in; when on (staging/production) every
guarded /api/* call needs a valid JWT whose role is permitted. Webhooks, /health
and /api/auth/* are never guarded.
"""
from __future__ import annotations

from fastapi import HTTPException, Request

from db import database
from db.repositories import users_repo
from services import auth as auth_svc
from settings import get_settings

# Anonymous principal used in dev (REQUIRE_AUTH=false) so guarded endpoints work
# without a login. Never returned when REQUIRE_AUTH=true.
_DEV_PRINCIPAL = {"id": None, "email": "dev@local", "role": "admin", "is_active": True}


def _bearer_token(request: Request) -> str | None:
    header = request.headers.get("authorization")
    if header and header.lower().startswith("bearer "):
        return header[7:].strip()
    return None


async def current_user(request: Request) -> dict | None:
    """Decode the Bearer token and load the (active) user, or None. Never raises."""
    settings = get_settings()
    payload = auth_svc.decode_access_token(
        _bearer_token(request), secret=settings.jwt_secret_effective
    )
    if not payload:
        return None
    if not database.is_supabase_mode():
        # No user store in SQLite mode — trust the signed token's claims (dev).
        return {"id": payload.get("sub"), "email": payload.get("email"),
                "role": payload.get("role"), "is_active": True,
                "facility_id": payload.get("facility_id")}
    user = await users_repo.get_by_id(payload.get("sub"))
    if not user or not user["is_active"]:
        return None
    return {"id": str(user["id"]), "email": user["email"], "role": user["role"],
            "is_active": True, "full_name": user.get("full_name"), "market": user.get("market"),
            "facility_id": str(user["facility_id"]) if user.get("facility_id") else None}


def require_roles(*roles: str):
    """Return a dependency that enforces one of `roles` (admin always allowed via
    the caller passing 'admin')."""
    async def _dep(request: Request) -> dict:
        settings = get_settings()
        user = await current_user(request)
        if not settings.require_auth:
            return user or _DEV_PRINCIPAL
        if user is None:
            raise HTTPException(status_code=401, detail="Authentication required.")
        if roles and user["role"] not in roles:
            raise HTTPException(status_code=403,
                                detail="You don't have access to this resource.")
        return user
    return _dep


require_admin = require_roles("admin")
require_ops = require_roles("admin", "operations")  # operations + admin


# --- Facility (partner dashboard) scoping ----------------------------------
# A facility principal used in dev (REQUIRE_AUTH=false) so the facility app works
# without a login, scoped to a seeded demo facility. Never used when auth is on.
_DEV_FACILITY_PRINCIPAL = {"id": None, "email": "facility-dev@local",
                           "role": "facility_owner", "is_active": True}


async def _dev_facility_id() -> str | None:
    """Resolve a facility to scope dev/admin callers to: FACILITY_DEV_ID if set,
    else the first active facility. Returns None outside Supabase mode."""
    settings = get_settings()
    if settings.facility_dev_id:
        return settings.facility_dev_id
    if not database.is_supabase_mode():
        return None
    return await database.fetchval(
        "select id::text from facilities where is_active order by created_at asc limit 1"
    )


async def _facility_exists(facility_id: str) -> bool:
    """True if a facility row with this id exists. Best-effort: any DB error
    (e.g. table absent in a non-Supabase environment) is treated as 'no', so an
    unknown/invalid override is ignored rather than raising."""
    try:
        return bool(await database.fetchval(
            "select exists(select 1 from facilities where id = $1)", facility_id
        ))
    except Exception:
        return False


async def require_facility_scope(request: Request) -> dict:
    """Facility-app guard. Returns the principal augmented with a resolved
    ``facility_id`` and 403s if the caller isn't bound to a facility. Every
    facility-scoped query MUST filter by this facility_id — the service role
    bypasses RLS, so isolation is enforced here + in application SQL, never by
    trusting a client-supplied facility_id.

    - REQUIRE_AUTH off (dev): anonymous is allowed as a facility_owner scoped to
      the seeded demo facility, so the app is usable without logging in.
    - REQUIRE_AUTH on: a facility_* user is locked to their own facility_id; an
      admin may target a facility via ?facility_id= (or the default facility).
    """
    settings = get_settings()
    user = await current_user(request)
    if not settings.require_auth:
        # Dev-only facility switcher: honor an X-Facility-Id header when it names
        # a real facility, so the dashboard can move between facilities without
        # editing .env. Gated to this (auth-off) branch — a client-supplied
        # facility is NEVER trusted once REQUIRE_AUTH is on (see below).
        override = (request.headers.get("x-facility-id") or "").strip()
        facility_id = None
        if override and await _facility_exists(override):
            facility_id = override
        facility_id = facility_id or (user or {}).get("facility_id") or await _dev_facility_id()
        if not facility_id:
            raise HTTPException(status_code=403,
                                detail="No facility is configured for this environment.")
        return {**(user or _DEV_FACILITY_PRINCIPAL), "facility_id": facility_id}
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required.")
    if user["role"] != "admin" and user["role"] not in auth_svc.FACILITY_ROLES:
        raise HTTPException(status_code=403, detail="Facility access required.")
    facility_id = user.get("facility_id")
    if user["role"] == "admin" and not facility_id:
        # Platform admin acting on a specific facility (validated: must exist).
        facility_id = request.query_params.get("facility_id") or await _dev_facility_id()
    if not facility_id:
        raise HTTPException(status_code=403, detail="Your account is not linked to a facility.")
    return {**user, "facility_id": facility_id}
