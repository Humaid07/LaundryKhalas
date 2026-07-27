"""Pending operational task types + SLA config (deterministic).

A conversational promise ("let me check with the facility", "I'll confirm with
Operations") must become a durable, tracked task — never chat-only (spec: the
agent must not say "I'll get back to you" unless a real pending task is created).
This module owns the task-type vocabulary + per-type SLA (due / follow-up /
escalation team) loaded from ``config/pending_tasks.json``. Persistence lives in
``db/repositories/pending_tasks_repo.py``.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_CONFIG_FILE = Path(__file__).resolve().parent.parent / "config" / "pending_tasks.json"

TASK_TYPES = frozenset({
    "AWAITING_FACILITY_QUOTE", "AWAITING_FACILITY_APPROVAL",
    "AWAITING_DRIVER_CONFIRMATION", "AWAITING_OPERATIONS_RESPONSE",
    "AWAITING_CUSTOMER_PHOTO", "AWAITING_CUSTOMER_LOCATION",
    "AWAITING_PAYMENT", "AWAITING_COMPLAINT_REVIEW",
})

# Safe default SLA when a type is missing from config.
_DEFAULT_SLA = {"due_hours": 6, "follow_up_hours": 3, "escalation_team": "Operations"}


@lru_cache(maxsize=1)
def _load_config() -> dict:
    with _CONFIG_FILE.open(encoding="utf-8") as fh:
        return json.load(fh)


def is_valid_type(task_type: str) -> bool:
    return task_type in TASK_TYPES


def get_sla(task_type: str) -> dict:
    """Per-type SLA: {due_hours, follow_up_hours, escalation_team}. Falls back to a
    safe default for an unknown type (the caller should still validate the type)."""
    return _load_config().get("task_types", {}).get(task_type, _DEFAULT_SLA)
