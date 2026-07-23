"""User management API — admin-only CRUD over public.users (dashboard RBAC).

Mounted with a router-level `require_admin` guard in main.py, so only admins
reach any endpoint here. Like /api/auth/login, user management requires
DATABASE_MODE=supabase (the users table lives in the dev/test Supabase project);
in SQLite dev mode these return 503 with a clear message.

Self-lockout protection: an admin cannot demote or deactivate their own account
(prevents removing the last admin by accident).
"""
from fastapi import APIRouter, Depends, HTTPException, Request

from api import deps
from db import database
from db.repositories import users_repo
from schemas import UserCreate, UserUpdate
from services.auth import ROLES, hash_password

router = APIRouter(prefix="/api/users", tags=["users"])


def _require_supabase() -> None:
    if not database.is_supabase_mode():
        raise HTTPException(
            status_code=503,
            detail="User management requires DATABASE_MODE=supabase.",
        )


def _validate_role(role: str) -> None:
    if role not in ROLES:
        raise HTTPException(
            status_code=422, detail=f"role must be one of {', '.join(ROLES)}."
        )


@router.get("")
async def list_users(request: Request):
    _require_supabase()
    return {"users": await users_repo.list_users(), "roles": list(ROLES)}


@router.post("", status_code=201)
async def create_user(payload: UserCreate, request: Request):
    _require_supabase()
    _validate_role(payload.role)
    email = (payload.email or "").strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=422, detail="A valid email is required.")
    if len(payload.password or "") < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters.")
    existing = await users_repo.get_by_email(email)
    if existing:
        raise HTTPException(status_code=409, detail="A user with that email already exists.")
    row = await users_repo.create(
        email=email, password_hash=hash_password(payload.password),
        full_name=payload.full_name, role=payload.role, market=payload.market,
    )
    return users_repo._public(row)


@router.patch("/{user_id}")
async def update_user(
    user_id: str, payload: UserUpdate, actor: dict = Depends(deps.require_admin)
):
    _require_supabase()
    if payload.role is not None:
        _validate_role(payload.role)

    # Self-lockout protection: never let an admin strip their own admin/active.
    is_self = actor.get("id") is not None and str(actor["id"]) == str(user_id)
    if is_self and payload.role is not None and payload.role != "admin":
        raise HTTPException(status_code=400, detail="You can't change your own role.")
    if is_self and payload.is_active is False:
        raise HTTPException(status_code=400, detail="You can't deactivate your own account.")

    updated = await users_repo.update_user(
        user_id, full_name=payload.full_name, role=payload.role, is_active=payload.is_active,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return updated
