"""Dashboard auth users (public.users).

Explicitly schema-qualified as ``public.users`` because Supabase ships a built-in
``auth.users`` table — we never want a bare ``users`` to resolve to that.
"""
from __future__ import annotations

from db import database

_SELECT = ("select id, email, password_hash, full_name, role, is_active, market, "
           "created_at, updated_at from public.users")


def _public(row: dict | None) -> dict | None:
    """User dict without the password hash (safe to return from the API)."""
    if not row:
        return None
    return {
        "id": str(row["id"]),
        "email": row["email"],
        "full_name": row.get("full_name"),
        "role": row["role"],
        "is_active": row["is_active"],
        "market": row.get("market"),
    }


async def get_by_email(email: str) -> dict | None:
    return await database.fetchrow(
        _SELECT + " where lower(email) = lower($1)", (email or "").strip()
    )


async def get_by_id(user_id: str) -> dict | None:
    return await database.fetchrow(_SELECT + " where id = $1", user_id)


async def create(
    *, email: str, password_hash: str, full_name: str | None, role: str,
    market: str | None = None, created_by_seed: bool = False,
) -> dict:
    return await database.fetchrow(
        """
        insert into public.users
            (email, password_hash, full_name, role, market, environment, created_by_seed)
        values (lower($1), $2, $3, $4, $5, 'dev', $6)
        on conflict (email) do update
            set password_hash = excluded.password_hash,
                full_name = excluded.full_name,
                role = excluded.role,
                market = excluded.market,
                is_active = true
        returning id, email, password_hash, full_name, role, is_active, market,
                  created_at, updated_at
        """,
        (email or "").strip(), password_hash, full_name, role, market, created_by_seed,
    )


async def list_users() -> list[dict]:
    rows = await database.fetch(_SELECT + " order by created_at asc")
    return [_public(r) for r in rows]


async def set_active(user_id: str, is_active: bool) -> dict | None:
    row = await database.fetchrow(
        "update public.users set is_active = $2 where id = $1 returning id, email, "
        "password_hash, full_name, role, is_active, market, created_at, updated_at",
        user_id, is_active,
    )
    return _public(row)
