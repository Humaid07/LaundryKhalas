"""Supabase/Postgres access layer — used only when DATABASE_MODE=supabase.

This is deliberately separate from the SQLite ORM layer in ``db/__init__.py``.
It talks to the dev/test Supabase Postgres directly via ``asyncpg`` using the
backend-only ``DATABASE_URL`` (service-role credentials). The frontend never
touches Supabase directly — Dashboard → FastAPI → Supabase.

The local SQLite path is untouched and keeps working. If ``asyncpg`` is not
installed or ``DATABASE_MODE`` is not ``supabase``, the Supabase helpers degrade
gracefully (health reports the state; repositories raise a clear error only if
actually called in supabase mode).
"""
from __future__ import annotations

import json
import ssl

from settings import get_settings

try:  # asyncpg is optional: only needed for supabase mode.
    import asyncpg
except ImportError:  # pragma: no cover - exercised only without the dep
    asyncpg = None  # type: ignore[assignment]

_pool: "asyncpg.Pool | None" = None  # type: ignore[name-defined]


def is_supabase_mode() -> bool:
    return get_settings().database_mode.lower() == "supabase"


def _dsn() -> str:
    """Normalize DATABASE_URL to a plain libpq DSN asyncpg understands
    (strips any SQLAlchemy ``+driver`` suffix and the ``postgres://`` alias)."""
    url = (get_settings().database_url or "").strip()
    for prefix in (
        "postgresql+asyncpg://",
        "postgresql+psycopg://",
        "postgresql+psycopg2://",
        "postgres+asyncpg://",
    ):
        if url.startswith(prefix):
            url = "postgresql://" + url[len(prefix):]
            break
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    return url


def _ssl_context() -> ssl.SSLContext:
    # Supabase requires TLS. For a dev/test project we establish an encrypted
    # connection without pinning the server certificate.
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


async def _init_conn(conn) -> None:
    # Decode json/jsonb columns to Python objects (asyncpg returns them as text
    # by default) so repositories get lists/dicts, not raw JSON strings.
    await conn.set_type_codec(
        "jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog"
    )
    await conn.set_type_codec(
        "json", encoder=json.dumps, decoder=json.loads, schema="pg_catalog"
    )


async def get_pool() -> "asyncpg.Pool":  # type: ignore[name-defined]
    global _pool
    if asyncpg is None:
        raise RuntimeError(
            "asyncpg is not installed — required for DATABASE_MODE=supabase. "
            "Install it (see apps/whatsapp-agent/pyproject.toml) to use the dev/test Supabase DB."
        )
    if _pool is None:
        dsn = _dsn()
        if not dsn.startswith("postgresql://"):
            raise RuntimeError(
                "DATABASE_URL is not a Postgres DSN. Set DATABASE_MODE=supabase and point "
                "DATABASE_URL at the dev/test Supabase connection string."
            )
        _pool = await asyncpg.create_pool(
            dsn=dsn, min_size=1, max_size=5, ssl=_ssl_context(), init=_init_conn
        )
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


# --------------------------------------------------------------------------
# Thin query helpers (repositories build on these)
# --------------------------------------------------------------------------
async def fetch(sql: str, *args) -> list[dict]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *args)
        return [dict(r) for r in rows]


async def fetchrow(sql: str, *args) -> dict | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(sql, *args)
        return dict(row) if row is not None else None


async def fetchval(sql: str, *args):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(sql, *args)


async def execute(sql: str, *args) -> str:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.execute(sql, *args)


async def db_health() -> dict:
    """Report DB mode + connectivity. Never raises — safe for /health/db."""
    settings = get_settings()
    mode = settings.database_mode
    info = {
        "mode": mode,
        "app_env": settings.app_env,
        "database_env": settings.database_env,
        "supabase_project_type": settings.supabase_project_type,
    }
    if not is_supabase_mode():
        info.update({"status": "ok", "backend": "sqlite", "connected": True})
        return info
    if asyncpg is None:
        info.update(
            {"status": "error", "backend": "supabase", "connected": False,
             "error": "asyncpg not installed"}
        )
        return info
    try:
        one = await fetchval("select 1")
        info.update({"status": "ok", "backend": "supabase", "connected": one == 1})
    except Exception as exc:  # noqa: BLE001 - health must never raise
        info.update(
            {"status": "error", "backend": "supabase", "connected": False, "error": str(exc)}
        )
    return info
