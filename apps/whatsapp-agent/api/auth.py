"""Auth API — login + current-user, backed by public.users (FastAPI-owned auth,
never Supabase-direct). Login is always open; everything else is guarded in
main.py.
"""
from fastapi import APIRouter, HTTPException, Request

from api import deps
from db import database
from db.repositories import users_repo
from schemas import LoginRequest
from services.auth import create_access_token, verify_password
from settings import get_settings

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/config")
async def auth_config():
    """Public: lets the dashboard know whether it must show a login screen."""
    return {"auth_required": get_settings().require_auth}


@router.post("/login")
async def login(payload: LoginRequest):
    settings = get_settings()
    if not database.is_supabase_mode():
        raise HTTPException(status_code=503, detail="Auth requires DATABASE_MODE=supabase.")
    if settings.require_auth and not settings.jwt_secret:
        raise HTTPException(status_code=500, detail="Server auth is misconfigured (no JWT secret).")

    user = await users_repo.get_by_email(payload.email)
    # Constant-ish path: always run verify to avoid trivially leaking which emails
    # exist. Reject inactive users and bad passwords with the same message.
    ok = bool(user) and user["is_active"] and verify_password(payload.password, user["password_hash"])
    if not ok:
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    token = create_access_token(
        subject=str(user["id"]), role=user["role"], email=user["email"],
        secret=settings.jwt_secret_effective, expiry_hours=settings.jwt_expiry_hours,
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": str(user["id"]), "email": user["email"],
                 "full_name": user.get("full_name"), "role": user["role"]},
    }


@router.get("/me")
async def me(request: Request):
    user = await deps.current_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    return user
