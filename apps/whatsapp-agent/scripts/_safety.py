"""Shared safety guards for the Supabase dev/test seed & reset scripts.

These are PURE functions (no DB, no I/O) so they can be unit-tested. They refuse
any destructive/seed action unless the environment is unambiguously the
DEV/TEST Supabase project. Production is never touched by these scripts.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow running as `python scripts/xxx.py` from apps/whatsapp-agent.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from settings import Settings, get_settings  # noqa: E402

SEED_BATCH_ID = "20260721_whatsapp_agent_seed_v1"
SEED_SOURCE = "whatsapp_agent_test_seed"

# Tables that carry seeded test data, child-before-parent for FK-safe deletes.
SEED_TABLES_DELETE_ORDER = [
    "agent_logs",
    "order_events",
    "approval_queue",
    "human_takeovers",
    "agent_flags",
    "tickets",
    "messages",
    "orders",
    "conversations",
    "customers",
]


def _base_problems(s: Settings) -> list[str]:
    problems: list[str] = []
    # The exact, required refusal message for the production case.
    if s.app_env.lower() == "production":
        problems.append("Refusing to seed test data into production environment.")
    if s.database_env.lower() != "test":
        problems.append(f"DATABASE_ENV must be 'test' (got '{s.database_env}').")
    if s.supabase_project_type.lower() != "test":
        problems.append(
            f"SUPABASE_PROJECT_TYPE must be 'test' (got '{s.supabase_project_type}')."
        )
    if s.database_mode.lower() != "supabase":
        problems.append(
            f"DATABASE_MODE must be 'supabase' to reach the dev/test project (got '{s.database_mode}')."
        )
    return problems


def check_seed_allowed(s: Settings | None = None) -> list[str]:
    """Return a list of blocking problems; empty means seeding is allowed."""
    s = s or get_settings()
    problems = _base_problems(s)
    if not s.allow_test_seed:
        problems.append("ALLOW_TEST_SEED must be true.")
    return problems


def check_reset_allowed(s: Settings | None = None) -> list[str]:
    """Return a list of blocking problems; empty means reset is allowed."""
    s = s or get_settings()
    problems = _base_problems(s)
    if not s.allow_test_reset:
        problems.append("ALLOW_TEST_RESET must be true.")
    return problems
