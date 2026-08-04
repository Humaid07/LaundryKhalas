"""Injectable replay clock.

The agent evaluates relative dates ("tomorrow", "tonight", "Friday") against a
notion of "now". For behavioural fidelity we set that clock to the ORIGINAL
conversation timestamp (HISTORICAL_DATE_CONTEXT) without ever mutating the
global system clock. The runner installs a clock override that the agent's time
helper reads (see runner.replay_runner for the wiring).

Market timezone for LaundryKhalas is Asia/Dubai (UAE) for the primary market.
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone, timedelta
from typing import Optional

# UAE market timezone (UTC+4, no DST).
DUBAI_TZ = timezone(timedelta(hours=4), name="Asia/Dubai")


class ReplayClock:
    """Thread-safe holder for the current replay 'now'.

    A single instance is installed per process; the runner sets the value at the
    start of each conversation (historical mode) or leaves it None (current-date
    mode -> agent uses real wall clock).
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._now: Optional[datetime] = None

    def set(self, value: Optional[datetime]) -> None:
        with self._lock:
            if value is not None and value.tzinfo is None:
                value = value.replace(tzinfo=DUBAI_TZ)
            self._now = value

    def clear(self) -> None:
        self.set(None)

    def now(self, tz: Optional[timezone] = None) -> datetime:
        with self._lock:
            base = self._now
        if base is None:
            base = datetime.now(timezone.utc)
        if tz is not None:
            return base.astimezone(tz)
        return base

    @property
    def is_overridden(self) -> bool:
        with self._lock:
            return self._now is not None


# Process-wide singleton the runner installs into the agent's time source.
_CLOCK = ReplayClock()


def get_clock() -> ReplayClock:
    return _CLOCK
