"""Backend-authoritative, timezone-aware clock for customer-facing scheduling.

The WhatsApp agent must NEVER use the server's UTC clock — or the LLM's internal
idea of "now" — for pickup scheduling. Every current-date / current-time /
relative-date decision resolves through here, in the customer's MARKET timezone
(UAE → Asia/Dubai, Qatar → Asia/Qatar, …).

Design:
  * ``now(market)`` returns a timezone-AWARE datetime in the market's zone.
  * A test/dev override (``settings.mock_now_iso`` or ``set_mock_now``) freezes
    the instant so slot-filtering and relative-date resolution are deterministic.
  * Zones resolve via ``zoneinfo.ZoneInfo`` (the ``tzdata`` package supplies the
    IANA database cross-platform). If a zone key is ever unavailable we fall back
    to the configured fixed offset for that market (Gulf zones have no DST, so
    the fixed offset is exact) rather than crashing a booking.

Nothing here reads the database; it is pure + cheap and safe to call per turn.
"""
from __future__ import annotations

import datetime as _dt
from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from settings import get_settings

# Market code / name → IANA timezone. Keys are matched case-insensitively and
# cover the common spellings the customer/order records use (market codes AE/QA
# and human names). Unknown markets fall back to the configured business tz.
MARKET_TIMEZONES: dict[str, str] = {
    "ae": "Asia/Dubai",
    "uae": "Asia/Dubai",
    "dubai": "Asia/Dubai",
    "abu dhabi": "Asia/Dubai",
    "sharjah": "Asia/Dubai",
    "ajman": "Asia/Dubai",
    "ras al khaimah": "Asia/Dubai",
    "qa": "Asia/Qatar",
    "qatar": "Asia/Qatar",
    "doha": "Asia/Qatar",
}

# Fixed-offset fallback (hours) per IANA zone, used ONLY if tzdata is missing.
# Gulf zones never observe DST, so these are always exact.
_FIXED_OFFSET_HOURS: dict[str, int] = {
    "Asia/Dubai": 4,
    "Asia/Qatar": 3,
}

# Test/dev in-process override. Prefer settings.mock_now_iso for config-driven
# freezing; set_mock_now() is for tests that need to sweep the clock.
_mock_now: _dt.datetime | None = None


def set_mock_now(instant: _dt.datetime | None) -> None:
    """Freeze (or clear) the scheduling clock in-process. Tests use this to make
    slot-filtering deterministic. ``instant`` should be timezone-aware."""
    global _mock_now
    _mock_now = instant


def _fixed_offset_zone(iana: str) -> _dt.tzinfo:
    hours = _FIXED_OFFSET_HOURS.get(iana, 4)  # default Gulf +04:00
    return _dt.timezone(_dt.timedelta(hours=hours), name=iana)


@lru_cache(maxsize=16)
def _zone(iana: str) -> _dt.tzinfo:
    try:
        return ZoneInfo(iana)
    except (ZoneInfoNotFoundError, ModuleNotFoundError, KeyError):
        return _fixed_offset_zone(iana)


def timezone_name_for_market(market: str | None) -> str:
    """Resolve the IANA timezone NAME for a market (default = business tz)."""
    default = get_settings().business_timezone or "Asia/Dubai"
    if not market:
        return default
    return MARKET_TIMEZONES.get(str(market).strip().lower(), default)


def zone_for_market(market: str | None) -> _dt.tzinfo:
    """Resolve the tzinfo for a market (ZoneInfo, or fixed-offset fallback)."""
    return _zone(timezone_name_for_market(market))


def _mock_instant() -> _dt.datetime | None:
    if _mock_now is not None:
        return _mock_now
    iso = (get_settings().mock_now_iso or "").strip()
    if not iso:
        return None
    try:
        parsed = _dt.datetime.fromisoformat(iso)
    except ValueError:
        return None
    # A naive mock instant is interpreted in the business timezone.
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_zone(get_settings().business_timezone or "Asia/Dubai"))
    return parsed


def now(market: str | None = None) -> _dt.datetime:
    """Current instant as a timezone-AWARE datetime in the market's zone.

    Honors the test/dev mock override; otherwise real wall-clock time converted
    into the market timezone (never naive, never UTC-as-local)."""
    zone = zone_for_market(market)
    mock = _mock_instant()
    if mock is not None:
        # Present the frozen instant in the requested market's zone.
        return mock.astimezone(zone)
    return _dt.datetime.now(zone)


def today(market: str | None = None) -> _dt.date:
    """Current calendar date in the market's zone."""
    return now(market).date()


def to_market(instant: _dt.datetime, market: str | None = None) -> _dt.datetime:
    """Convert any datetime to the market zone (assumes UTC if naive)."""
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=_dt.timezone.utc)
    return instant.astimezone(zone_for_market(market))


def combine(date: _dt.date, time: _dt.time, market: str | None = None) -> _dt.datetime:
    """Combine a date + wall-clock time into a market-zone aware datetime."""
    return _dt.datetime.combine(date, time, tzinfo=zone_for_market(market))
