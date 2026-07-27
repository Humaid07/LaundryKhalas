"""Facility notification service tests: mock-first gating, idempotency, the
'live blocked unless ready' rule, and the PII-safe preview.
"""
from types import SimpleNamespace

from db.repositories import facility_notifications_repo
from services import facility_notifications as fn


class _FakeSettings:
    def __init__(self, mode="mock", ready=False):
        self.facility_notifications_mode_normalized = mode
        self.facility_notifications_ready = ready


def _patch_settings(monkeypatch, *, mode="mock", ready=False):
    monkeypatch.setattr(fn, "get_settings", lambda: _FakeSettings(mode, ready))


def _patch_repo(monkeypatch, *, exists=False, dedupe_exists=False):
    calls = []

    async def fake_exists(facility_id, order_uuid, type):
        return exists

    async def fake_dedupe(facility_id, dedupe_key):
        return dedupe_exists

    async def fake_create(**kw):
        calls.append(kw)
        return {"id": "n1", **kw}

    monkeypatch.setattr(facility_notifications_repo, "exists_for_order", fake_exists)
    monkeypatch.setattr(facility_notifications_repo, "exists_by_dedupe", fake_dedupe)
    monkeypatch.setattr(facility_notifications_repo, "create", fake_create)
    return calls


# --------------------------- preview privacy ------------------------------
def test_new_order_preview_has_no_pii():
    preview = fn._new_order_preview({
        "order_id": "LK-2026-000004", "service": "Wash & Fold",
        "area": "Dubai Marina",
        # these must never appear in the preview:
        "customer_phone": "+971501234567",
        "pickup_address": "Villa 12, Street 4",
    })
    assert "LK-2026-000004" in preview
    assert "+971501234567" not in preview
    assert "Villa 12" not in preview


# --------------------------- mock mode logs, never sends (9-11) -----------
async def test_new_assignment_logs_mock_row(monkeypatch):
    _patch_settings(monkeypatch, mode="mock", ready=False)
    calls = _patch_repo(monkeypatch)
    order = {"id": "u1", "order_id": "LK-2026-000004", "service": "Wash & Fold",
             "area": "Dubai Marina"}
    await fn.notify_new_order_assigned("FAC-1", order)
    assert len(calls) == 1
    # Mock mode: logged only — never an external channel.
    assert calls[0]["channel"] == "mock"
    assert calls[0]["status"] == "mock_logged"
    assert calls[0]["type"] == "new_order_assigned"


async def test_notify_is_idempotent_per_order_type(monkeypatch):
    _patch_settings(monkeypatch, mode="mock", ready=False)
    calls = _patch_repo(monkeypatch, exists=True)  # already logged
    result = await fn.notify("FAC-1", "new_order_assigned", order_uuid="u1")
    assert result is None
    assert calls == []  # no duplicate row


# --------------------------- live blocked unless ready (12) ---------------
async def test_live_channel_blocked_when_not_ready(monkeypatch):
    # mode=whatsapp but the channel is NOT ready → must fall back to mock_logged.
    _patch_settings(monkeypatch, mode="whatsapp", ready=False)
    calls = _patch_repo(monkeypatch)
    await fn.notify("FAC-1", "sla_risk", order_uuid="u2")
    assert calls[0]["status"] == "mock_logged"
    assert calls[0]["channel"] == "mock"


async def test_live_channel_used_only_when_ready(monkeypatch):
    _patch_settings(monkeypatch, mode="whatsapp", ready=True)
    calls = _patch_repo(monkeypatch)
    await fn.notify("FAC-1", "sla_risk", order_uuid="u3")
    # Ready → the row is queued on the live channel (status pending), not mock.
    assert calls[0]["channel"] == "whatsapp"
    assert calls[0]["status"] == "pending"


# --------------------------- new triggers: status / driver / issue --------
async def test_status_update_logs_and_has_no_pii(monkeypatch):
    _patch_settings(monkeypatch, mode="mock", ready=False)
    calls = _patch_repo(monkeypatch)
    order = {"id": "u1", "order_id": "LK-2026-000004", "turnaround_text": "24-48h",
             "customer_phone": "+971501234567", "pickup_address": "Villa 12, Street 4"}
    await fn.notify_order_status_updated("FAC-1", order, old_status="picked_up",
                                         new_status="in_cleaning")
    assert len(calls) == 1
    assert calls[0]["type"] == "order_status_updated"
    assert calls[0]["status"] == "mock_logged"
    assert calls[0]["dedupe_key"] == "u1:status:in_cleaning"
    preview = calls[0]["message_preview"]
    assert "LK-2026-000004" in preview and "In cleaning" in preview
    assert "+971501234567" not in preview and "Villa 12" not in preview


async def test_status_update_idempotent_via_dedupe(monkeypatch):
    _patch_settings(monkeypatch, mode="mock", ready=False)
    calls = _patch_repo(monkeypatch, dedupe_exists=True)  # same status already logged
    result = await fn.notify_order_status_updated(
        "FAC-1", {"id": "u1", "order_id": "LK-9"}, new_status="in_cleaning")
    assert result is None
    assert calls == []


async def test_driver_assigned_preview_has_no_pii(monkeypatch):
    _patch_settings(monkeypatch, mode="mock", ready=False)
    calls = _patch_repo(monkeypatch)
    order = {"id": "u1", "order_id": "LK-AE-1042", "customer_phone": "+971501234567",
             "pickup_address": "Villa 12"}
    await fn.notify_driver_assigned("FAC-1", order, task_type="facility_handoff",
                                    expected_completion="Today 6:30 PM", driver_id="d1")
    assert calls[0]["type"] == "driver_assigned"
    assert calls[0]["dedupe_key"] == "u1:driver:d1:facility_handoff"
    p = calls[0]["message_preview"]
    assert "LK-AE-1042" in p and "facility handoff" in p
    assert "+971501234567" not in p and "Villa 12" not in p


async def test_internal_issue_reply_no_pii(monkeypatch):
    _patch_settings(monkeypatch, mode="mock", ready=False)
    calls = _patch_repo(monkeypatch)
    issue = {"id": "i1", "order_ref": "LK-AE-1042",
             "message": "internal secret note about the customer phone +971501234567"}
    await fn.notify_internal_issue_reply("FAC-1", issue, message_id="m1")
    assert calls[0]["type"] == "internal_issue_reply"
    assert calls[0]["issue_uuid"] == "i1"
    assert calls[0]["dedupe_key"] == "issue:i1:reply:m1"
    p = calls[0]["message_preview"]
    assert "LK-AE-1042" in p
    assert "internal secret note" not in p and "+971501234567" not in p


async def test_notify_never_raises_on_repo_error(monkeypatch):
    _patch_settings(monkeypatch, mode="mock", ready=False)

    async def boom(**kw):
        raise RuntimeError("db down")

    async def no_exist(*a):
        return False

    monkeypatch.setattr(facility_notifications_repo, "exists_for_order", no_exist)
    monkeypatch.setattr(facility_notifications_repo, "create", boom)
    # Must swallow the error and return None (notifications never break the caller).
    assert await fn.notify("FAC-1", "sla_risk", order_uuid="u4") is None
