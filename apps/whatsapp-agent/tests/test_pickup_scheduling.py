"""Timezone-aware pickup scheduling: clock authority, availability filtering,
temporal-intent resolution, and the Claude booking-tool integration.

The reference scenario is the reported bug: a customer says "Are you available
now to pickup?" at ~1:03 PM Dubai time. The agent must resolve TODAY, never
re-ask the day, exclude passed / lead-violating windows, and offer only valid
future windows.
"""
import datetime as _dt
import json

import pytest

from agents.whatsapp_agent.booking_tools import BookingContext, make_booking_executor
from services import booking_flow as bf
from services import clock
from services import pickup_availability as pav
from services import pickup_datetime as pdt

# The 5 configured windows (mirrors the pickup_slots seed), WITH times so the
# time-of-day filter is actually exercised.
WINDOWS = [
    {"slot_id": "morning_08_11", "label": "8:00 AM - 11:00 AM",
     "start_time": _dt.time(8, 0), "end_time": _dt.time(11, 0)},
    {"slot_id": "midday_11_14", "label": "11:00 AM - 2:00 PM",
     "start_time": _dt.time(11, 0), "end_time": _dt.time(14, 0)},
    {"slot_id": "afternoon_14_17", "label": "2:00 PM - 5:00 PM",
     "start_time": _dt.time(14, 0), "end_time": _dt.time(17, 0)},
    {"slot_id": "evening_17_20", "label": "5:00 PM - 8:00 PM",
     "start_time": _dt.time(17, 0), "end_time": _dt.time(20, 0)},
    {"slot_id": "night_20_22", "label": "8:00 PM - 10:00 PM",
     "start_time": _dt.time(20, 0), "end_time": _dt.time(22, 0)},
]

TODAY = _dt.date(2026, 7, 28)              # a Tuesday


def _now(h, m=0, market="AE"):
    return clock.combine(TODAY, _dt.time(h, m), market)


async def _all_windows(date, area, service_id):
    return [dict(w) for w in WINDOWS]


async def _no_windows(date, area, service_id):
    return []


# ===================== clock authority =====================================
def test_market_timezones_resolve():
    assert clock.timezone_name_for_market("AE") == "Asia/Dubai"
    assert clock.timezone_name_for_market("Dubai") == "Asia/Dubai"
    assert clock.timezone_name_for_market("QA") == "Asia/Qatar"
    assert clock.timezone_name_for_market(None) == "Asia/Dubai"      # default
    assert clock.timezone_name_for_market("Narnia") == "Asia/Dubai"  # fallback


def test_server_utc_still_schedules_in_dubai():
    """Server clock in UTC must not leak a 4-hour error into scheduling."""
    utc_1am = _dt.datetime(2026, 7, 28, 21, 0, tzinfo=_dt.timezone.utc)  # 01:00 next day Dubai
    clock.set_mock_now(utc_1am)
    try:
        assert clock.now("AE").hour == 1              # 21:00Z + 4 = 01:00 Dubai
        assert clock.today("AE") == _dt.date(2026, 7, 29)
        assert clock.now("QA").hour == 0              # +3 = 00:00 Qatar
    finally:
        clock.set_mock_now(None)


def test_datetimes_are_timezone_aware():
    assert clock.now("AE").tzinfo is not None
    assert clock.combine(TODAY, _dt.time(9, 0), "AE").utcoffset() == _dt.timedelta(hours=4)


# ===================== availability filtering ==============================
async def test_available_at_1pm_excludes_passed_and_lead_violating():
    av = await pav.get_availability(TODAY, now_local=_now(13, 3),
                                    slots_provider=_all_windows, market="AE", lead_minutes=60)
    assert av.earliest_bookable_at.strftime("%H:%M") == "14:03"
    ids = [s.slot_id for s in av.slots]
    assert ids == ["evening_17_20", "night_20_22"]             # only future, lead-satisfying
    reasons = {s.slot_id: s.reason for s in av.all_slots}
    assert reasons["morning_08_11"] == "PAST_SLOT"
    assert reasons["midday_11_14"] == "LEAD_TIME"              # 11:00 start < 14:03
    assert reasons["afternoon_14_17"] == "LEAD_TIME"           # 14:00 start < 14:03
    assert av.same_day_cutoff_passed is False


async def test_available_at_9am_applies_lead_time_not_just_end_time():
    av = await pav.get_availability(TODAY, now_local=_now(9, 0),
                                    slots_provider=_all_windows, market="AE", lead_minutes=60)
    ids = [s.slot_id for s in av.slots]
    # 8-11 excluded (starts 08:00 < 10:00 earliest); 11-2 onward valid.
    assert "morning_08_11" not in ids
    assert ids[0] == "midday_11_14"


async def test_future_date_keeps_all_windows():
    av = await pav.get_availability(TODAY + _dt.timedelta(days=1), now_local=_now(13, 3),
                                    slots_provider=_all_windows, market="AE")
    assert len(av.slots) == len(WINDOWS)                       # future date: no time filter
    assert av.is_same_day is False


async def test_no_same_day_returns_next_available_date():
    av = await pav.get_availability(TODAY, now_local=_now(23, 30),
                                    slots_provider=_all_windows, market="AE", lead_minutes=60)
    assert av.slots == []
    assert av.same_day_cutoff_passed is True
    assert av.next_available_date == TODAY + _dt.timedelta(days=1)


async def test_allow_active_slot_booking_flag():
    av = await pav.get_availability(TODAY, now_local=_now(18, 30),
                                    slots_provider=_all_windows, market="AE",
                                    lead_minutes=60, allow_active_slot=True)
    # 17-20 is active at 18:30; with the flag it stays eligible.
    assert "evening_17_20" in [s.slot_id for s in av.slots]


# ===================== temporal intent resolution ==========================
def test_now_resolves_to_today_earliest():
    r = pdt.resolve("Are you available now to pickup?", now=_now(13, 3), market="AE")
    assert r.intent_type == pdt.INTENT_IMMEDIATE
    assert r.resolved_date == TODAY and r.same_day and r.immediate
    assert r.reason_code == pdt.REASON_RESOLVED_TODAY


@pytest.mark.parametrize("phrase", [
    "pickup now", "available now", "can you collect now", "send someone now",
    "can the driver come today", "today pickup", "as soon as possible",
])
def test_same_day_phrases_resolve_today(phrase):
    r = pdt.resolve(phrase, now=_now(13, 3), market="AE")
    assert r.resolved_date == TODAY and r.same_day


def test_tomorrow_morning_resolves_absolute_date_and_daypart():
    r = pdt.resolve("tomorrow morning", now=_now(13, 3), market="AE")
    assert r.resolved_date == TODAY + _dt.timedelta(days=1)
    assert r.preferred_daypart == "morning"
    assert r.reason_code == pdt.REASON_RESOLVED_TOMORROW


def test_today_after_six_is_lower_bound():
    r = pdt.resolve("today after 6", now=_now(13, 3), market="AE")
    assert r.resolved_date == TODAY
    assert r.lower_bound_time == _dt.time(18, 0)


def test_in_two_hours_is_relative_to_backend_now():
    r = pdt.resolve("in two hours", now=_now(13, 3), market="AE")
    assert r.reason_code == pdt.REASON_RESOLVED_RELATIVE_TIME
    assert r.preferred_exact_time == _dt.time(15, 3)


def test_yesterday_is_past_and_needs_clarification():
    r = pdt.resolve("yesterday", now=_now(13, 3), market="AE")
    assert r.valid is False
    assert r.reason_code == pdt.REASON_PAST_DATE_INVALID
    assert r.clarification_required is True
    assert r.resolved_date is None                            # never silently -> today


def test_1130_selected_after_it_passed_is_rejected():
    r = pdt.resolve("ok then ready for 11 30", now=_now(13, 3), market="AE", existing_date=TODAY)
    assert r.valid is False
    assert r.reason_code == pdt.REASON_PAST_TIME_INVALID
    assert "11:30 AM" in (r.message or "")


def test_1130_before_it_passes_is_valid():
    r = pdt.resolve("ready for 11 30", now=_now(9, 30), market="AE", existing_date=TODAY)
    assert r.valid is True
    assert r.preferred_exact_time == _dt.time(11, 30)


def test_next_weekday_is_future_not_today():
    r = pdt.resolve("next monday", now=_now(13, 3), market="AE")   # Tue 28 Jul
    assert r.resolved_date == _dt.date(2026, 8, 3)                 # the coming Monday
    assert r.resolved_date > TODAY


# ===================== FSM date parser integration =========================
def test_parse_pickup_date_now_is_today():
    d, reason = bf.parse_pickup_date(bf.Inbound(text="pickup now"), TODAY,
                                     now=_now(13, 3), market="AE")
    assert reason == "ok" and d == TODAY


def test_parse_pickup_date_yesterday_is_past():
    d, reason = bf.parse_pickup_date(bf.Inbound(text="yesterday"), TODAY,
                                     now=_now(13, 3), market="AE")
    assert reason == "past" and d is None


# ===================== Claude booking-tool integration =====================
class _FakeRepo:
    def __init__(self):
        self.row = None

    async def get_active_draft(self, conv_id):
        return self.row

    async def start_booking(self, conv_id, customer):
        self.row = {"id": "o1", "conversation_state": bf.WAITING_FOR_SERVICE,
                    "order_id": "LK-TEST-1", "service_id": "WASH_FOLD",
                    "service": "Wash & Fold", "line_items": [{"item_code": "x", "name": "Shirt",
                    "quantity": 2, "line_kind": "final"}], "customer_name": "Sara"}
        return self.row

    async def apply_booking_updates(self, oid, updates, state):
        self.row.update(updates)
        self.row["conversation_state"] = state
        return self.row


def _executor(now):
    repo = _FakeRepo()
    ctx = BookingContext(
        conversation_id="c1", order_uuid="o1", repo=repo, today=now.date(),
        available_slots=_all_windows, customer={"id": "c", "market": "AE"},
        verified_name="Sara", now=now, market="AE")
    return repo, make_booking_executor(ctx)


async def _call(execute, name, ti=None):
    out, err = await execute(name, ti or {})
    return json.loads(out), err


async def test_state_block_carries_backend_clock():
    repo, execute = _executor(_now(13, 3))
    await repo.start_booking("c1", None)
    data, err = await _call(execute, "get_current_workflow")
    wf = data["workflow"]
    assert wf["timezone"] == "Asia/Dubai"
    assert wf["current_local_datetime"].startswith("2026-07-28T13:03")
    assert wf["minimum_lead_time_minutes"] == 60


async def test_save_pickup_date_now_persists_today_and_drops_from_missing():
    repo, execute = _executor(_now(13, 3))
    await repo.start_booking("c1", None)
    data, err = await _call(execute, "save_pickup_date", {"date_text": "now"})
    assert not err
    assert data["pickup_date"] == "2026-07-28" and data["same_day"] is True
    # The day is resolved → it must NOT reappear as a missing field (no re-ask).
    assert "pickup_date" not in data["workflow"]["missing_fields"]


async def test_get_available_pickup_slots_tool_excludes_passed_windows():
    repo, execute = _executor(_now(13, 3))
    await repo.start_booking("c1", None)
    await _call(execute, "save_pickup_date", {"date_text": "today"})
    data, err = await _call(execute, "get_available_pickup_slots")
    assert not err
    labels = [s["label"] for s in data["available_slots"]]
    assert labels == ["5:00 PM - 8:00 PM", "8:00 PM - 10:00 PM"]
    assert not any("8:00 AM" in lbl for lbl in labels)        # no passed morning window


async def test_save_pickup_time_rejects_passed_window_and_persists_bounds():
    repo, execute = _executor(_now(13, 3))
    await repo.start_booking("c1", None)
    await _call(execute, "save_pickup_date", {"date_text": "today"})
    # A passed window is not offered → cannot be saved.
    _, err = await _call(execute, "save_pickup_time", {"slot": "morning_08_11"})
    assert err
    # A valid future window saves + records absolute start/end (a WINDOW, not ETA).
    data, err2 = await _call(execute, "save_pickup_time", {"slot": "evening_17_20"})
    assert not err2
    assert data["pickup_slot_id"] == "evening_17_20"
    assert data["confirmed_slot_start"].startswith("2026-07-28T17:00")
    assert repo.row["pickup_start_time"].hour == 17


async def test_resolve_tool_flags_yesterday():
    repo, execute = _executor(_now(13, 3))
    await repo.start_booking("c1", None)
    data, err = await _call(execute, "resolve_pickup_datetime_intent", {"phrase": "yesterday"})
    assert not err
    assert data["valid"] is False and data["reason_code"] == "PAST_DATE_INVALID"


async def test_no_same_day_offers_next_date_via_tool():
    repo = _FakeRepo()
    ctx = BookingContext(
        conversation_id="c1", order_uuid="o1", repo=repo, today=TODAY,
        available_slots=_all_windows, customer={"id": "c", "market": "AE"},
        verified_name="Sara", now=_now(23, 45), market="AE")
    execute = make_booking_executor(ctx)
    await repo.start_booking("c1", None)
    await _call(execute, "save_pickup_date", {"date_text": "today"})
    data, err = await _call(execute, "get_available_pickup_slots")
    assert data["available_slots"] == []
    assert data["next_available_date"] == "2026-07-29"
