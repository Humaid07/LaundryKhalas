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
    # Start clean. The teardown delete below is best-effort and, on Windows, can
    # be skipped when the async SQLite engine still holds the file handle
    # (WinError 32). A DB left over from a crashed/interrupted prior run would
    # then leak stale rows/schema into this run and break demo-order seeding
    # (UNIQUE constraint failed: orders.order_id). Deleting at session start
    # guarantees a hermetic run regardless of how the previous one ended.
    try:
        _TEST_DB_PATH.unlink(missing_ok=True)
    except PermissionError:
        pass
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
    """Give every test a pristine agent database: the demo orders
    (LK-AE-1024..1027) and NO leftover transactional state.

    ALL agent state (orders, conversations, messages, agent logs) lives in the
    shared session database, so a reset that clears only orders lets a
    booking/conversation from one test leak into the next (e.g. a later test
    sees a mid-booking reply instead of a greeting), and residual demo-order
    rows collide with the re-seed (UNIQUE constraint failed: orders.order_id
    during autoflush). Clearing every transactional table in one committed
    transaction before re-seeding keeps each test hermetic regardless of run
    order or how a previous run ended. Catalogue/pricing reference tables are
    left intact.
    """
    from sqlalchemy import delete

    from db import AsyncSessionLocal, init_db
    from models import AgentLog, Conversation, Message, Order
    from services import order_store

    await init_db()
    async with AsyncSessionLocal() as session:
        # Children before parents (messages/orders reference conversations).
        for model in (Message, AgentLog, Order, Conversation):
            await session.execute(delete(model))
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
