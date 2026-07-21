"""MVP admin authentication.

This is a deliberately simple placeholder: a shared API key checked via a
request header. It exists so admin-only routes are not wide open, not to be
a production auth system. Replace with real user auth (SSO/JWT + roles)
before any live launch - tracked in docs/checklists/live-whatsapp-readiness.md.
"""
from fastapi import Header, HTTPException, status

from app.core.config import get_settings


async def require_admin(x_admin_api_key: str | None = Header(default=None)) -> str:
    settings = get_settings()
    if not x_admin_api_key or x_admin_api_key != settings.admin_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid admin API key (X-Admin-Api-Key header).",
        )
    return x_admin_api_key
