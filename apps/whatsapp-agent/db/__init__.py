"""Async SQLAlchemy engine/session setup (SQLite local mode).

This package keeps the original `from db import Base, get_db, init_db,
AsyncSessionLocal` surface working exactly as before — SQLite by default for
the standalone MVP and its test suite. The Supabase/Postgres access layer used
when DATABASE_MODE=supabase lives alongside it in `db.database` +
`db.repositories.*` and does NOT change this local path.
"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from settings import get_settings

settings = get_settings()


def _orm_url(raw: str) -> str:
    """SQLAlchemy needs an explicit async driver. A bare ``postgresql://`` URL
    would default to psycopg2 (sync, not installed). In supabase mode the ORM
    engine is not used for queries (the asyncpg layer in ``db.database`` is), but
    it must still be constructible at import — so map bare Postgres URLs to the
    installed asyncpg driver. SQLite/local URLs pass through unchanged.
    """
    if raw.startswith("postgresql://"):
        return "postgresql+asyncpg://" + raw[len("postgresql://"):]
    if raw.startswith("postgres://"):
        return "postgresql+asyncpg://" + raw[len("postgres://"):]
    return raw


engine = create_async_engine(_orm_url(settings.database_url), echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db() -> None:
    import models  # noqa: F401  (ensures models are registered on Base.metadata)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
