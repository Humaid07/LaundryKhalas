"""Phase 3: the DISCOUNT_OBJECTION follow-up type + scheduling (spec §8/§21)."""
import datetime as _dt
from zoneinfo import ZoneInfo

import pytest

from services import followups as fu
from services import followup_scheduler as sched


@pytest.fixture(autouse=True)
def _fresh():
    fu.reload_config()
    yield
    fu.reload_config()


def _at(y, mo, d, h, mi=0):
    return _dt.datetime(y, mo, d, h, mi, tzinfo=ZoneInfo("Asia/Dubai"))


def test_type_constant_exists():
    assert fu.DISCOUNT_OBJECTION == "DISCOUNT_OBJECTION"


def test_offset_is_within_five_to_seven_minutes():
    assert 5 <= fu.offset_minutes(fu.DISCOUNT_OBJECTION) <= 7


def test_type_is_prioritised():
    # present in the arbitration priority list (not sorted last)
    order = fu._config().get("priority", [])
    assert fu.DISCOUNT_OBJECTION in order


def test_builder_row_shape_and_payload():
    anchor = _at(2026, 8, 8, 15, 0)
    row = sched.discount_objection_row(
        "conv-1", anchor, market="AE", persona="Zoya", order_id="ord-1",
        customer_phone="+9715xxx", quote_version=3, trigger_message_id="m-42")
    assert row["followup_type"] == fu.DISCOUNT_OBJECTION
    assert row["order_id"] == "ord-1"
    assert row["due_at"] == anchor + _dt.timedelta(minutes=6)  # 6 min, inside window
    assert row["dedupe_key"] == fu.dedupe_key("conv-1", fu.DISCOUNT_OBJECTION)
    assert row["payload"]["quote_version"] == 3
    assert row["payload"]["trigger_message_id"] == "m-42"
    assert row["payload"]["trigger_type"] == fu.DISCOUNT_OBJECTION


def test_suppressed_when_order_confirmed_or_replied():
    ok, reason = fu.is_suppressed(fu.DISCOUNT_OBJECTION,
                                  fu.SuppressionContext(order_confirmed=True))
    assert ok and reason == "already_ordered"
    ok2, reason2 = fu.is_suppressed(fu.DISCOUNT_OBJECTION,
                                    fu.SuppressionContext(customer_replied=True))
    assert ok2 and reason2 == "customer_replied"


def test_not_suppressed_when_still_open():
    ok, _ = fu.is_suppressed(fu.DISCOUNT_OBJECTION, fu.SuppressionContext())
    assert ok is False
