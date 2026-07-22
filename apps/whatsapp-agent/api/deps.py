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
                "role": payload.get("role"), "is_active": True}
    user = await users_repo.get_by_id(payload.get("sub"))
    if not user or not user["is_active"]:
        return None
    return {"id": str(user["id"]), "email": user["email"], "role": user["role"],
            "is_active": True, "full_name": user.get("full_name"), "market": user.get("market")}


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
