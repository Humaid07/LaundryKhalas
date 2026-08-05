"""Follow-up scheduler orchestration (services/followup_scheduler, spec §§14, 24, 25)."""
import datetime as _dt

import pytest

from services import clock
from services import followups as fu
from services import followup_scheduler as fs

_TZ = clock.zone_for_market("AE")


def _at(y, mo, d, h, mi=0):
    return _dt.datetime(y, mo, d, h, mi, tzinfo=_TZ)


@pytest.fixture(autouse=True)
def _fresh():
    fu.reload_config()
    yield
    fu.reload_config()


# --- scheduling builders -----------------------------------------------------
def test_payment_silence_rows_two_followups_with_due_times():
    anchor = _at(2026, 8, 5, 14, 0)
    rows = fs.payment_silence_rows("c1", anchor, market="AE", persona="Sara")
    assert [r["followup_type"] for r in rows] == [fu.PAYMENT_STRIPE, fu.PAYMENT_CASH]
    assert rows[0]["due_at"] == _at(2026, 8, 5, 14, 6)    # +6 min
    assert rows[1]["due_at"] == _at(2026, 8, 5, 14, 15)   # +15 min
    assert all(r["status"] == fs.PENDING for r in rows)
    # dedupe keys are distinct per type and stable
    assert rows[0]["dedupe_key"] != rows[1]["dedupe_key"]


def test_web_abandonment_rows_three_followups():
    click = _at(2026, 8, 5, 10, 0)
    rows = fs.web_abandonment_rows("c9", click, market="AE", persona="Maya", customer_phone="+9715...")
    assert [r["followup_type"] for r in rows] == [
        fu.WEB_ABANDONMENT_1, fu.WEB_ABANDONMENT_2, fu.WEB_ABANDONMENT_3]
    assert rows[0]["due_at"] == _at(2026, 8, 5, 10, 10)   # +10 min
    assert rows[1]["due_at"] == _at(2026, 8, 5, 10, 40)   # +40 min
    assert rows[2]["due_at"] == _at(2026, 8, 5, 16, 40)   # +400 min (6h after fu2)


def test_quote_inactivity_row_due_time_and_dedupe():
    row = fs.quote_inactivity_row("c2", _at(2026, 8, 5, 15, 0), persona="Zoya")
    assert row["followup_type"] == fu.QUOTE_INACTIVITY
    assert row["due_at"] == _at(2026, 8, 5, 15, 6)
    assert row["dedupe_key"] == fu.dedupe_key("c2", fu.QUOTE_INACTIVITY)


def test_pickup_reminder_row_is_slot_relative():
    pickup = _at(2026, 8, 6, 18, 0)   # tomorrow, 6 PM window
    row = fs.pickup_reminder_row("c3", pickup, hours_before=2, market="AE")
    assert row["followup_type"] == fu.PICKUP_REMINDER
    assert row["due_at"] == _at(2026, 8, 6, 16, 0)   # 2h before, inside the window
    assert row["dedupe_key"] == fu.dedupe_key("c3", fu.PICKUP_REMINDER)


def test_pickup_reminder_before_window_shifts_to_window_start():
    pickup = _at(2026, 8, 6, 9, 0)    # 9 AM window; 2h before = 7 AM (before 8 AM)
    row = fs.pickup_reminder_row("c4", pickup, hours_before=2, market="AE")
    assert row["due_at"] == _at(2026, 8, 6, 8, 0)   # shifted to window start


# --- sweeping: one send per conversation, most relevant ----------------------
def _row(id, conv, ftype, due, persona="Sara"):
    return {"id": id, "conversation_id": conv, "followup_type": ftype, "due_at": due,
            "template_id": ftype, "persona": persona, "customer_phone": "+9715"}


def test_plan_conversation_sends_highest_priority_due():
    now = _at(2026, 8, 5, 15, 0)
    rows = [
        _row("f1", "c1", fu.WEB_ABANDONMENT_1, _at(2026, 8, 5, 14, 50)),
        _row("f2", "c1", fu.PAYMENT_STRIPE, _at(2026, 8, 5, 14, 55)),
    ]
    plan = fs.plan_conversation(rows, {}, now, market="AE")
    assert plan.followup_type == fu.PAYMENT_STRIPE
    assert plan.followup_id == "f2"
    assert plan.text == fu.FOLLOWUP_TEMPLATES[fu.PAYMENT_STRIPE]


def test_plan_conversation_none_when_all_suppressed():
    now = _at(2026, 8, 5, 15, 0)
    rows = [_row("f1", "c1", fu.PAYMENT_STRIPE, _at(2026, 8, 5, 14, 55))]
    ctx = {fu.PAYMENT_STRIPE: fu.SuppressionContext(customer_replied=True)}
    assert fs.plan_conversation(rows, ctx, now, market="AE") is None


def test_plan_batch_one_send_per_conversation():
    now = _at(2026, 8, 5, 15, 0)
    rows = [
        _row("a1", "c1", fu.PAYMENT_STRIPE, _at(2026, 8, 5, 14, 55)),
        _row("a2", "c1", fu.WEB_ABANDONMENT_1, _at(2026, 8, 5, 14, 50)),  # same conv, lower prio
        _row("b1", "c2", fu.WEB_ABANDONMENT_1, _at(2026, 8, 5, 14, 40)),
    ]
    plans = fs.plan_batch(rows, lambda c, t: fu.SuppressionContext(), now, market="AE")
    by_conv = {p.conversation_id: p for p in plans}
    assert len(plans) == 2                                   # one per conversation
    assert by_conv["c1"].followup_type == fu.PAYMENT_STRIPE  # most relevant for c1
    assert by_conv["c2"].followup_type == fu.WEB_ABANDONMENT_1


def test_plan_batch_respects_per_conversation_suppression():
    now = _at(2026, 8, 5, 15, 0)
    rows = [
        _row("a1", "c1", fu.PAYMENT_STRIPE, _at(2026, 8, 5, 14, 55)),
        _row("b1", "c2", fu.PAYMENT_STRIPE, _at(2026, 8, 5, 14, 55)),
    ]

    def ctx(conv, ftype):
        # c1's customer already paid → suppress; c2 still pending.
        return fu.SuppressionContext(paid=(conv == "c1"))

    plans = fs.plan_batch(rows, ctx, now, market="AE")
    assert [p.conversation_id for p in plans] == ["c2"]
