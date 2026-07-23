"""Granular pricing permissions, mapped onto the two RBAC roles.

The dashboard has two roles (admin, operations). Rather than a separate grant
table, pricing capability is expressed as named permissions and mapped to the
roles here — so access is enforced by *permission* in the backend (not just by
hiding buttons), and a real per-user grant table can replace this map later
without changing call sites.

  admin       → every pricing permission (create/edit/publish/rollback/import/export)
  operations  → view + prepare a DRAFT (create/edit) + export; NEVER publish,
                rollback, import, or deactivate live pricing (publish is the gate).
"""
from __future__ import annotations

from fastapi import HTTPException, Request

from api import deps

VIEW = "pricing.view"
CREATE = "pricing.create"
EDIT = "pricing.edit"
PUBLISH = "pricing.publish"
ROLLBACK = "pricing.rollback"
IMPORT = "pricing.import"
EXPORT = "pricing.export"

ALL = (VIEW, CREATE, EDIT, PUBLISH, ROLLBACK, IMPORT, EXPORT)

_ROLE_PERMS: dict[str, frozenset[str]] = {
    "admin": frozenset(ALL),
    "operations": frozenset({VIEW, CREATE, EDIT, EXPORT}),
}


def permissions_for(role: str | None) -> frozenset[str]:
    return _ROLE_PERMS.get(role or "", frozenset())


def can(role: str | None, permission: str) -> bool:
    return permission in permissions_for(role)


def require_pricing(permission: str):
    """FastAPI dependency enforcing ONE pricing permission. Gated by REQUIRE_AUTH
    exactly like the role guards: off → synthetic dev admin (all perms); on →
    a valid token whose role grants the permission, else 401/403."""
    async def _dep(request: Request) -> dict:
        from settings import get_settings

        settings = get_settings()
        user = await deps.current_user(request)
        if not settings.require_auth:
            return user or {"id": None, "email": "dev@local", "role": "admin"}
        if user is None:
            raise HTTPException(status_code=401, detail="Authentication required.")
        if not can(user.get("role"), permission):
            raise HTTPException(status_code=403,
                                detail=f"You don't have the {permission} permission.")
        return user
    return _dep
