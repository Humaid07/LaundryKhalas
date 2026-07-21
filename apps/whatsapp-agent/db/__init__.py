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

engine = create_async_engine(settings.database_url, echo=False)
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
