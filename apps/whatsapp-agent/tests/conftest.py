import os
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

_TEST_DB_PATH = Path(__file__).resolve().parent / "test_whatsapp_agent.db"
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{_TEST_DB_PATH}")
os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("WHATSAPP_MODE", "mock")
os.environ.setdefault("META_WHATSAPP_VERIFY_TOKEN", "test-verify-token")
# Pin tests to local SQLite mode regardless of what a developer's .env sets
# (e.g. DATABASE_MODE=supabase for live work) so the suite stays hermetic.
os.environ.setdefault("DATABASE_MODE", "sqlite")


@pytest.fixture(autouse=True, scope="session")
def _cleanup_test_db():
    yield
    # On Windows the async SQLite engine may still hold the file handle at
    # session teardown (WinError 32). Best-effort delete: never fail the run
    # over a leftover test artifact.
    try:
        _TEST_DB_PATH.unlink(missing_ok=True)
    except PermissionError:
        pass


@pytest_asyncio.fixture(autouse=True)
async def _reset_orders():
    """Give every test a pristine set of demo orders (LK-AE-1024..1027).

    Orders live in the shared session database, so without this a booking or
    a cancel/change request in one test would leak into the next. Reset +
    reseed before each test keeps the order-flow tests deterministic
    regardless of run order.
    """
    from sqlalchemy import delete

    from db import AsyncSessionLocal, init_db
    from models import Order
    from services import order_store

    await init_db()
    async with AsyncSessionLocal() as session:
        await session.execute(delete(Order))
        await session.commit()
        await order_store.seed_demo_orders(session)
    yield


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    from main import app

    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
