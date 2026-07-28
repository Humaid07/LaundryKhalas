"""Backend-authoritative pickup availability engine.

The customer/LLM is NEVER allowed to invent or list a pickup window. This module
takes the raw bookable slots for a date (from ``slots_repo.available_slots`` —
weekday/emirate/service/capacity already applied) and layers the TIME-aware rules
the raw query cannot express:

  * For the current local date, a window is only offered if it has not passed AND
    its start satisfies the configured minimum lead time
    (earliest_bookable = now + lead). Future dates keep all their windows.
  * Reports the same-day cutoff state, the earliest bookable instant, stable
    machine-readable slot ids, and — when no same-day window remains — the next
    date that has availability.

Everything is timezone-aware via ``services.clock`` (market zone). Pure aside from
the injected async ``slots_provider`` (so it is unit-testable offline).
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass

from services import clock
from settings import get_settings

# How many days ahead to search for the next available date when the same day is
# fully passed / booked.
_NEXT_DATE_HORIZON_DAYS = 14


@dataclass(frozen=True)
class SlotView:
    slot_id: str
    label: str
    start_time: _dt.time
    end_time: _dt.time
    start_at: _dt.datetime          # market-zone aware
    end_at: _dt.datetime
    eligible: bool
    reason: str                      # ELIGIBLE | PAST_SLOT | LEAD_TIME | ...
    capacity_status: str = "available"

    def as_dict(self) -> dict:
        return {
            "slot_id": self.slot_id,
            "label": self.label,
            "start_time": self.start_time.strftime("%H:%M"),
            "end_time": self.end_time.strftime("%H:%M"),
            "start_at": self.start_at.isoformat(),
            "end_at": self.end_at.isoformat(),
            "eligible": self.eligible,
            "reason": self.reason,
            "capacity_status": self.capacity_status,
        }


@dataclass(frozen=True)
class Availability:
    timezone: str
    current_local_datetime: _dt.datetime
    resolved_pickup_date: _dt.date
    is_same_day: bool
    same_day_cutoff_passed: bool
    minimum_lead_time_minutes: int
    earliest_bookable_at: _dt.datetime
    slots: list[SlotView]                 # eligible slots only (display order)
    all_slots: list[SlotView]             # eligible + filtered (for diagnostics/logs)
    next_available_date: _dt.date | None  # set only when no same-day slot remains

    @property
    def eligible_slots(self) -> list[SlotView]:
        return self.slots

    def as_dict(self) -> dict:
        return {
            "timezone": self.timezone,
            "current_local_datetime": self.current_local_datetime.isoformat(),
            "resolved_pickup_date": self.resolved_pickup_date.isoformat(),
            "is_same_day": self.is_same_day,
            "same_day_cutoff_passed": self.same_day_cutoff_passed,
            "minimum_lead_time_minutes": self.minimum_lead_time_minutes,
            "earliest_bookable_at": self.earliest_bookable_at.isoformat(),
            "available_slots": [s.as_dict() for s in self.slots],
            "next_available_date": (
                self.next_available_date.isoformat() if self.next_available_date else None
            ),
        }


def _eligibility(
    slot: dict,
    pickup_date: _dt.date,
    now_local: _dt.datetime,
    earliest_bookable: _dt.datetime,
    market: str | None,
    allow_active_slot: bool,
) -> SlotView:
    start_t, end_t = slot.get("start_time"), slot.get("end_time")
    if start_t is None or end_t is None:
        # A slot with no time-of-day info can't be time-filtered — pass it through
        # rather than crash. Production slots (slots_repo) always carry times.
        return SlotView(
            slot_id=slot.get("slot_id", ""), label=slot.get("label", ""),
            start_time=start_t or _dt.time(0, 0), end_time=end_t or _dt.time(0, 0),
            start_at=now_local, end_at=now_local, eligible=True, reason="NO_TIME_INFO",
        )
    start_at = clock.combine(pickup_date, start_t, market)
    end_at = clock.combine(pickup_date, end_t, market)
    # Windows crossing midnight (end <= start) roll the end to the next day.
    if end_at <= start_at:
        end_at = end_at + _dt.timedelta(days=1)

    is_same_day = pickup_date == now_local.date()
    reason = "ELIGIBLE"
    eligible = True
    if is_same_day:
        if end_at <= now_local:
            reason, eligible = "PAST_SLOT", False
        elif allow_active_slot and start_at <= now_local < end_at:
            reason, eligible = "ACTIVE_SLOT", True          # inside the window, allowed
        elif start_at < earliest_bookable:
            reason, eligible = "LEAD_TIME", False           # starts too soon
    return SlotView(
        slot_id=slot["slot_id"], label=slot["label"],
        start_time=slot["start_time"], end_time=slot["end_time"],
        start_at=start_at, end_at=end_at, eligible=eligible, reason=reason,
    )


async def get_availability(
    pickup_date: _dt.date,
    *,
    now_local: _dt.datetime,
    slots_provider,                     # async (date, area, service_id) -> [slot dict]
    area: str | None = None,
    service_id: str | None = None,
    market: str | None = None,
    lead_minutes: int | None = None,
    allow_active_slot: bool | None = None,
    find_next_when_empty: bool = True,
) -> Availability:
    """Compute time-aware availability for ``pickup_date`` at ``now_local``.

    ``now_local`` MUST be a timezone-aware datetime in the market zone (use
    ``services.clock.now(market)``). ``slots_provider`` is the raw slot query
    (already weekday/emirate/service/capacity filtered)."""
    settings = get_settings()
    if lead_minutes is None:
        lead_minutes = int(settings.pickup_minimum_lead_time_minutes)
    if allow_active_slot is None:
        allow_active_slot = bool(settings.pickup_allow_active_slot_booking)

    tz_name = clock.timezone_name_for_market(market)
    earliest_bookable = now_local + _dt.timedelta(minutes=lead_minutes)
    is_same_day = pickup_date == now_local.date()

    raw = await slots_provider(pickup_date, area, service_id)
    views = [
        _eligibility(s, pickup_date, now_local, earliest_bookable, market, allow_active_slot)
        for s in raw
    ]
    eligible = [v for v in views if v.eligible]

    # Same-day cutoff = it's today and nothing bookable remains today.
    same_day_cutoff_passed = is_same_day and not eligible

    next_date = None
    if not eligible and find_next_when_empty:
        next_date = await _find_next_available_date(
            start_after=pickup_date, now_local=now_local, slots_provider=slots_provider,
            area=area, service_id=service_id, market=market,
            lead_minutes=lead_minutes, allow_active_slot=allow_active_slot,
        )

    return Availability(
        timezone=tz_name,
        current_local_datetime=now_local,
        resolved_pickup_date=pickup_date,
        is_same_day=is_same_day,
        same_day_cutoff_passed=same_day_cutoff_passed,
        minimum_lead_time_minutes=lead_minutes,
        earliest_bookable_at=earliest_bookable,
        slots=eligible,
        all_slots=views,
        next_available_date=next_date,
    )


async def _find_next_available_date(
    *, start_after: _dt.date, now_local: _dt.datetime, slots_provider,
    area, service_id, market, lead_minutes, allow_active_slot,
) -> _dt.date | None:
    """Scan forward for the next date (after ``start_after``) that has at least
    one eligible slot. Future dates never fail the time filter, so the first date
    with any slot rows wins."""
    for offset in range(1, _NEXT_DATE_HORIZON_DAYS + 1):
        d = start_after + _dt.timedelta(days=offset)
        raw = await slots_provider(d, area, service_id)
        if not raw:
            continue
        earliest = now_local + _dt.timedelta(minutes=lead_minutes)
        for s in raw:
            v = _eligibility(s, d, now_local, earliest, market, allow_active_slot)
            if v.eligible:
                return d
    return None
