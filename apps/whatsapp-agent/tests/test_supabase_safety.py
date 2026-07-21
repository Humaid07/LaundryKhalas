"""Tests for the Supabase dev/test seed/reset safety guards and the new
Supabase-backed endpoints' graceful behaviour in local SQLite mode.

These run WITHOUT any database connection: the guards are pure functions, and
the endpoints must degrade cleanly when DATABASE_MODE != supabase.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import _safety  # noqa: E402
from settings import Settings  # noqa: E402


def _dev_test_settings(**over) -> Settings:
    base = dict(
        app_env="development",
        database_env="test",
        database_mode="supabase",
        supabase_project_type="test",
        allow_test_seed=True,
        allow_test_reset=True,
    )
    base.update(over)
    return Settings(**base)


# ------------------------------- seed guards -------------------------------
def test_seed_allowed_when_dev_test():
    assert _safety.check_seed_allowed(_dev_test_settings()) == []


def test_seed_refused_without_allow_flag():
    problems = _safety.check_seed_allowed(_dev_test_settings(allow_test_seed=False))
    assert any("ALLOW_TEST_SEED" in p for p in problems)


def test_seed_refused_in_production_with_exact_message():
    problems = _safety.check_seed_allowed(_dev_test_settings(app_env="production"))
    assert "Refusing to seed test data into production environment." in problems


def test_seed_refused_when_not_supabase_mode():
    problems = _safety.check_seed_allowed(_dev_test_settings(database_mode="sqlite"))
    assert any("DATABASE_MODE" in p for p in problems)


# ------------------------------- reset guards ------------------------------
def test_reset_allowed_when_dev_test():
    assert _safety.check_reset_allowed(_dev_test_settings()) == []


def test_reset_refused_without_allow_flag():
    problems = _safety.check_reset_allowed(_dev_test_settings(allow_test_reset=False))
    assert any("ALLOW_TEST_RESET" in p for p in problems)


def test_reset_refused_wrong_project_type():
    problems = _safety.check_reset_allowed(_dev_test_settings(supabase_project_type="production"))
    assert any("SUPABASE_PROJECT_TYPE" in p for p in problems)


def test_reset_refused_wrong_database_env():
    problems = _safety.check_reset_allowed(_dev_test_settings(database_env="staging"))
    assert any("DATABASE_ENV" in p for p in problems)


def test_delete_order_is_child_before_parent():
    order = _safety.SEED_TABLES_DELETE_ORDER
    # customers/conversations (parents) must be deleted last.
    assert order.index("messages") < order.index("conversations")
    assert order.index("orders") < order.index("customers")
    assert order.index("order_events") < order.index("orders")


# --------------------- endpoints in local SQLite mode ----------------------
async def test_health_db_endpoint_sqlite(client):
    r = await client.get("/health/db")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["backend"] == "sqlite"


async def test_conversations_list_empty_in_sqlite(client):
    r = await client.get("/api/conversations")
    assert r.status_code == 200
    assert r.json() == []


async def test_flags_list_empty_in_sqlite(client):
    r = await client.get("/api/flags")
    assert r.status_code == 200
    assert r.json() == []


async def test_human_takeover_requires_supabase(client):
    r = await client.post("/api/conversations/some-id/human-takeover")
    assert r.status_code == 503
