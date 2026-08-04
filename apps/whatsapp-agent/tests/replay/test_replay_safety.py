"""Tests for the fail-closed safety guard and capture-only transport."""
from __future__ import annotations

import types

import pytest

from replay_harness.core.config import ReplayConfig
from replay_harness.safety import capture_channel, guard


# --- capture channel -------------------------------------------------------
@pytest.fixture
def installed_capture():
    sink = capture_channel.install()
    sink.reset()
    yield sink
    capture_channel.uninstall()


async def test_capture_channel_records_and_never_sends(installed_capture):
    # A channel built with a bogus URL must NOT attempt any network I/O.
    from channels.evolution_whatsapp import EvolutionWhatsAppChannel

    ch = EvolutionWhatsAppChannel(base_url="http://127.0.0.1:9/x", api_key="k", instance="i")
    result = await ch.send_text(to_phone="+971500000000", text="hello")
    assert result.status == "captured"
    assert installed_capture.count() == 1
    assert installed_capture.all()[0].text == "hello"


async def test_capture_from_settings_also_captured(installed_capture):
    from channels.evolution_whatsapp import EvolutionWhatsAppChannel

    ch = EvolutionWhatsAppChannel.from_settings()
    await ch.send_text(to_phone="+971500000000", text="via from_settings")
    assert installed_capture.count() == 1


async def test_capture_self_test_passes(installed_capture):
    assert await capture_channel.self_test() is True
    # self_test cleans up after itself.
    assert installed_capture.count() == 0


async def test_context_attribution(installed_capture):
    from channels.evolution_whatsapp import EvolutionWhatsAppChannel

    ch = EvolutionWhatsAppChannel(base_url="x", api_key="k", instance="i")
    installed_capture.set_context("conv-A")
    await ch.send_text(to_phone="+1", text="a")
    installed_capture.set_context("conv-B")
    await ch.send_text(to_phone="+2", text="b")
    installed_capture.clear_context()
    assert installed_capture.latest_text("conv-A") == "a"
    assert installed_capture.latest_text("conv-B") == "b"


# --- guard: fail-closed ----------------------------------------------------
def _safe_settings():
    return types.SimpleNamespace(
        database_env="test",
        supabase_project_type="test",
        database_mode="supabase",
        database_url="postgresql://user:pw@db.test.supabase.co:5432/postgres",
        facility_notifications_mode="mock",
        whatsapp_agent_mode="test",
    )


def _safe_config():
    return ReplayConfig()  # defaults are all safe


def test_guard_passes_when_safe(monkeypatch):
    monkeypatch.setattr(guard, "_get_settings", _safe_settings)
    monkeypatch.setenv("APP_ENV", "dev")
    problems = guard.collect_problems(
        _safe_config(), capture_installed=True, capture_self_test_passed=True
    )
    assert problems == []


def test_guard_blocks_production_env(monkeypatch):
    monkeypatch.setattr(guard, "_get_settings", _safe_settings)
    monkeypatch.setenv("APP_ENV", "production")
    problems = guard.collect_problems(
        _safe_config(), capture_installed=True, capture_self_test_passed=True
    )
    assert any("production" in p for p in problems)


def test_guard_blocks_when_capture_not_installed(monkeypatch):
    monkeypatch.setattr(guard, "_get_settings", _safe_settings)
    monkeypatch.setenv("APP_ENV", "dev")
    problems = guard.collect_problems(
        _safe_config(), capture_installed=False, capture_self_test_passed=False
    )
    assert any("Capture-only outbound channel is not installed" in p for p in problems)


def test_guard_blocks_non_test_db(monkeypatch):
    s = _safe_settings()
    s.database_env = "production"
    s.supabase_project_type = "production"
    monkeypatch.setattr(guard, "_get_settings", lambda: s)
    monkeypatch.setenv("APP_ENV", "dev")
    problems = guard.collect_problems(
        _safe_config(), capture_installed=True, capture_self_test_passed=True
    )
    assert any("DATABASE_ENV" in p for p in problems)
    assert any("SUPABASE_PROJECT_TYPE" in p for p in problems)


def test_guard_blocks_real_send_flag(monkeypatch):
    monkeypatch.setattr(guard, "_get_settings", _safe_settings)
    monkeypatch.setenv("APP_ENV", "dev")
    cfg = _safe_config()
    cfg.allow_real_sends = True
    problems = guard.collect_problems(
        cfg, capture_installed=True, capture_self_test_passed=True
    )
    assert any("ALLOW_REAL_SENDS" in p for p in problems)


def test_guard_blocks_production_db_url(monkeypatch):
    s = _safe_settings()
    s.database_url = "postgresql://user:pw@db.prod.supabase.co:5432/postgres"
    monkeypatch.setattr(guard, "_get_settings", lambda: s)
    monkeypatch.setenv("APP_ENV", "dev")
    problems = guard.collect_problems(
        _safe_config(), capture_installed=True, capture_self_test_passed=True
    )
    assert any("production database" in p for p in problems)


async def test_enforce_raises_when_unsafe(monkeypatch):
    s = _safe_settings()
    s.database_mode = "sqlite"
    monkeypatch.setattr(guard, "_get_settings", lambda: s)
    monkeypatch.setenv("APP_ENV", "dev")
    with pytest.raises(guard.ReplaySafetyError):
        await guard.enforce(ReplayConfig())
    capture_channel.uninstall()
