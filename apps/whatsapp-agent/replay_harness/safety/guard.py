"""Fail-closed startup safety guard for the replay harness.

The replay MUST refuse to run (fail closed) if there is any chance of a real
side effect. Modeled on scripts/_safety.py. Checks are pure and return a list of
blocking problems; `enforce()` raises `ReplaySafetyError` if any exist.

Blocks unless ALL hold:
  * environment is not production
  * DATABASE_ENV == test and SUPABASE_PROJECT_TYPE == test
  * DATABASE_MODE == supabase (booking path requires it; a stray prod URL is
    still caught by the test-env checks above)
  * capture-only mode enabled and the capture channel installed + self-tested
  * every real-side-effect flag is false (sends/payments/notifications/
    facility dispatch/driver dispatch/production db writes)
  * facility notifications are in mock mode
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from ..core.config import ReplayConfig


class ReplaySafetyError(RuntimeError):
    """Raised when the replay environment is not provably safe."""


def _get_settings():
    from settings import get_settings

    return get_settings()


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name, default) or "").strip().lower()


def collect_problems(cfg: ReplayConfig, *, capture_installed: bool,
                     capture_self_test_passed: bool) -> list[str]:
    problems: list[str] = []

    # --- environment must be a verified test environment --------------------
    app_env = _env("APP_ENV", "dev")
    if app_env == "production" or app_env == "prod":
        problems.append("APP_ENV indicates production")

    s = _get_settings()
    database_env = (getattr(s, "database_env", "") or "").lower()
    project_type = (getattr(s, "supabase_project_type", "") or "").lower()
    database_mode = (getattr(s, "database_mode", "") or "").lower()

    if database_env != "test":
        problems.append(f"DATABASE_ENV must be 'test' (got {database_env!r})")
    if project_type != "test":
        problems.append(f"SUPABASE_PROJECT_TYPE must be 'test' (got {project_type!r})")
    if database_mode != "supabase":
        problems.append(
            f"DATABASE_MODE must be 'supabase' for the replay booking path (got {database_mode!r})"
        )

    # A crude production-URL heuristic on top of the env flags above.
    db_url = (getattr(s, "database_url", "") or "").lower()
    for marker in ("prod", "production"):
        if marker in db_url:
            problems.append("DATABASE_URL appears to reference a production database")
            break

    # --- capture-only + no real side effects --------------------------------
    if not cfg.replay_mode:
        problems.append("WHATSAPP_REPLAY_MODE must be true")
    if not cfg.capture_only:
        problems.append("WHATSAPP_REPLAY_CAPTURE_ONLY must be true")
    if cfg.allow_real_sends:
        problems.append("WHATSAPP_REPLAY_ALLOW_REAL_SENDS must be false")
    if cfg.allow_real_payments:
        problems.append("WHATSAPP_REPLAY_ALLOW_REAL_PAYMENTS must be false")
    if cfg.allow_real_notifications:
        problems.append("WHATSAPP_REPLAY_ALLOW_REAL_NOTIFICATIONS must be false")
    if cfg.allow_real_facility_dispatch:
        problems.append("WHATSAPP_REPLAY_ALLOW_REAL_FACILITY_DISPATCH must be false")
    if cfg.allow_real_driver_dispatch:
        problems.append("WHATSAPP_REPLAY_ALLOW_REAL_DRIVER_DISPATCH must be false")
    if cfg.allow_production_db_writes:
        problems.append("WHATSAPP_REPLAY_ALLOW_PRODUCTION_DB_WRITES must be false")

    # --- facility notifications must be mock ---------------------------------
    fac_mode = (getattr(s, "facility_notifications_mode", "mock") or "mock").lower()
    if fac_mode != "mock":
        problems.append(f"FACILITY_NOTIFICATIONS_MODE must be 'mock' (got {fac_mode!r})")

    # --- capture channel installed & proven ---------------------------------
    if not capture_installed:
        problems.append("Capture-only outbound channel is not installed")
    if not capture_self_test_passed:
        problems.append("Capture channel self-test did not pass (a real send might occur)")

    # --- agent mode must be test (not live) ---------------------------------
    agent_mode = (getattr(s, "whatsapp_agent_mode", "paused") or "paused").lower()
    if agent_mode == "live":
        problems.append("WHATSAPP_AGENT_MODE must not be 'live' during replay")

    # --- enum sanity --------------------------------------------------------
    problems.extend(cfg.validate_enums())

    return problems


@dataclass
class GuardResult:
    ok: bool
    problems: list[str]


async def install_and_verify(cfg: ReplayConfig) -> GuardResult:
    """Install capture transport, run its self-test, then collect safety problems."""
    from . import capture_channel

    capture_channel.install()
    self_test_ok = await capture_channel.self_test()
    problems = collect_problems(
        cfg,
        capture_installed=capture_channel.is_installed(),
        capture_self_test_passed=self_test_ok,
    )
    return GuardResult(ok=not problems, problems=problems)


async def enforce(cfg: ReplayConfig) -> None:
    """Install + verify; raise ReplaySafetyError (fail closed) if not safe."""
    result = await install_and_verify(cfg)
    if not result.ok:
        bullet = "\n  - ".join(result.problems)
        raise ReplaySafetyError(
            "Replay refused to start — environment is not provably safe:\n  - "
            + bullet
            + "\n\nThe replay FAILS CLOSED rather than risk a real side effect. "
            "Fix the above and retry."
        )
