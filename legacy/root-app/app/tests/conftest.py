"""Test bootstrap.

Tests must never run against the same database as local dev/seed data -
this module points the app's database engine at a dedicated
`<dbname>_test` database (created here if missing) *before* any app module
is imported, so app.db.session's engine binds to it from the start. Do not
import any `app.*` module above the `os.environ["DATABASE_URL"]` override
below, or it will bind to the dev database instead.
"""
import asyncio
import os
from urllib.parse import urlsplit, urlunsplit

import asyncpg

_ORIGINAL_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://laundrykhalas:changeme_local_only@postgres:5432/laundrykhalas",
)
_base, _, _dbname = _ORIGINAL_DATABASE_URL.rpartition("/")
_TEST_DB_NAME = f"{_dbname}_test"
os.environ["DATABASE_URL"] = f"{_base}/{_TEST_DB_NAME}"


def _maintenance_dsn(url: str) -> str:
    plain = url.replace("postgresql+asyncpg://", "postgresql://")
    parts = urlsplit(plain)
    return urlunsplit((parts.scheme, parts.netloc, "/postgres", "", ""))


async def _ensure_test_database_exists() -> None:
    conn = await asyncpg.connect(dsn=_maintenance_dsn(_ORIGINAL_DATABASE_URL))
    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", _TEST_DB_NAME)
        if not exists:
            await conn.execute(f'CREATE DATABASE "{_TEST_DB_NAME}"')
    finally:
        await conn.close()


asyncio.run(_ensure_test_database_exists())

# Safe to import app modules from here on - DATABASE_URL now points at the
# dedicated test database.
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import AsyncSessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import *  # noqa: F401,F403,E402 - ensures all tables are registered
from app.models.facility import Facility  # noqa: E402
from app.models.market import CountryConfig, Market  # noqa: E402

_MOCK_PRICING = {
    "services": {
        "wash_and_fold": {"unit": "kg", "price_per_unit": 6.0, "min_price": 25.0},
        "dry_cleaning": {"unit": "item", "price_per_unit": 12.0, "min_price": 25.0},
        "ironing": {"unit": "item", "price_per_unit": 4.0, "min_price": 15.0},
    }
}
_MOCK_OPERATING_HOURS = {"open": "09:00", "close": "21:00", "pickup_window_hours": 3}


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        market = Market(
            code="AE",
            name="United Arab Emirates",
            country="United Arab Emirates",
            timezone="Asia/Dubai",
            currency="AED",
            default_language="en",
            is_active=True,
        )
        db.add(market)
        await db.flush()

        db.add(
            CountryConfig(
                market_id=market.id,
                whatsapp_phone_number="+9715000000AE",
                default_service_area="Dubai",
                operating_hours_json=_MOCK_OPERATING_HOURS,
                pricing_config_json=_MOCK_PRICING,
                policy_config_json={"note": "mock test policy"},
            )
        )
        db.add(
            Facility(
                market_id=market.id,
                name="[MOCK TEST] Marina Facility",
                area="Marina",
                city="Dubai",
                capacity_daily=50,
                is_active=True,
                ppi_score=4.5,
            )
        )
        await db.commit()

    yield

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def admin_headers():
    settings = get_settings()
    return {"X-Admin-Api-Key": settings.admin_api_key}


@pytest_asyncio.fixture
async def ae_market_id():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Market).where(Market.code == "AE"))
        return result.scalar_one().id
