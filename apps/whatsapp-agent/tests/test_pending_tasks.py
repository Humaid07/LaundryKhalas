"""Pending-task SLA config + repo guard tests."""
import pytest

from db import database
from db.repositories import pending_tasks_repo
from services import pending_tasks as tasks_svc


def test_all_seven_plus_types_present():
    expected = {
        "AWAITING_FACILITY_QUOTE", "AWAITING_FACILITY_APPROVAL",
        "AWAITING_DRIVER_CONFIRMATION", "AWAITING_OPERATIONS_RESPONSE",
        "AWAITING_CUSTOMER_PHOTO", "AWAITING_CUSTOMER_LOCATION",
        "AWAITING_PAYMENT", "AWAITING_COMPLAINT_REVIEW",
    }
    assert expected <= tasks_svc.TASK_TYPES


def test_is_valid_type():
    assert tasks_svc.is_valid_type("AWAITING_FACILITY_QUOTE")
    assert not tasks_svc.is_valid_type("AWAITING_UNICORN")


def test_get_sla_known_and_default():
    sla = tasks_svc.get_sla("AWAITING_DRIVER_CONFIRMATION")
    assert sla["due_hours"] == 2 and "escalation_team" in sla
    # Unknown → safe default, never a KeyError.
    d = tasks_svc.get_sla("AWAITING_NOPE")
    assert d["due_hours"] == 6


def test_config_covers_every_task_type():
    cfg = tasks_svc._load_config()["task_types"]
    for t in tasks_svc.TASK_TYPES:
        assert t in cfg, f"config missing SLA for {t}"


async def test_create_rejects_unknown_type():
    with pytest.raises(ValueError):
        await pending_tasks_repo.create("AWAITING_UNICORN", customer_id="c1")


async def test_create_uses_sla_hours(monkeypatch):
    captured = {}

    async def fake_fetchrow(sql, *args):
        captured["sql"] = sql
        captured["args"] = args
        return None

    monkeypatch.setattr(database, "fetchrow", fake_fetchrow)
    await pending_tasks_repo.create("AWAITING_COMPLAINT_REVIEW", customer_id="c1",
                                    conversation_id="cv1")
    # due/follow-up are computed DB-side from SLA hours passed as strings.
    assert "now() + ($9 || ' hours')::interval" in captured["sql"]
    # AWAITING_COMPLAINT_REVIEW SLA = due 4h, follow-up 2h.
    assert captured["args"][8] == "4" and captured["args"][9] == "2"
