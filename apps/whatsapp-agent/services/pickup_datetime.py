"""Deterministic backend resolver for temporal pickup phrases.

Claude (or the FSM) may extract the customer's raw temporal words, but the
BACKEND resolves them into an actual date / time using the market-local current
datetime — never the LLM's assumed clock. This module is PURE: given a phrase +
a timezone-aware ``now`` it returns a structured intent.

It deliberately handles the RELATIVE / natural phrases the strict calendar parser
(``services.booking_flow.parse_pickup_date``) does not: now / asap / today /
tonight / this evening / later today / tomorrow[ morning] / day after tomorrow /
yesterday / named weekday / "in two hours" / "after an hour" / "after six" /
"around 5" / "at 7 tonight". Explicit calendar dates (27/07, "5 August") still
flow through the calendar parser.

The availability engine (services.pickup_availability) decides which *windows*
satisfy an intent; this resolver only fixes the DATE and any preferred time/daypart
and flags past dates/times.
"""
from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass

# --- Intent + reason vocabularies -------------------------------------------
INTENT_IMMEDIATE = "IMMEDIATE"                 # "now", "send someone now"
INTENT_EARLIEST = "EARLIEST_AVAILABLE"         # "asap", "earliest available"
INTENT_EXACT_TIME = "EXACT_TIME"               # "at 7pm", "11:30"
INTENT_TIME_RANGE = "TIME_RANGE"               # "after 6", "between 5 and 8"
INTENT_DAYPART = "DAYPART"                      # "this evening", "tomorrow morning"
INTENT_RELATIVE_TIME = "RELATIVE_TIME"         # "in two hours"
INTENT_FLEXIBLE_SAME_DAY = "FLEXIBLE_SAME_DAY" # "today", "can you collect today"
INTENT_DATE_ONLY = "DATE_ONLY"                 # "tomorrow", a resolved weekday
INTENT_NONE = "NONE"                           # not a temporal phrase we resolve

REASON_RESOLVED_TODAY = "RESOLVED_TODAY"
REASON_RESOLVED_TOMORROW = "RESOLVED_TOMORROW"
REASON_RESOLVED_DATE = "RESOLVED_DATE"
REASON_RESOLVED_WEEKDAY = "RESOLVED_WEEKDAY"
REASON_RESOLVED_RELATIVE_TIME = "RESOLVED_RELATIVE_TIME"
REASON_PAST_DATE_INVALID = "PAST_DATE_INVALID"
REASON_PAST_TIME_INVALID = "PAST_TIME_INVALID"
REASON_AMBIGUOUS_TIME = "AMBIGUOUS_TIME"
REASON_NOT_TEMPORAL = "NOT_TEMPORAL"

_DAYPARTS = ("morning", "afternoon", "evening", "night")
_WEEKDAYS = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
    "mon": 0, "tue": 1, "tues": 1, "wed": 2, "thu": 3, "thur": 3, "thurs": 3,
    "fri": 4, "sat": 5, "sun": 6,
}
_NUM_WORDS = {
    "an": 1, "a": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "half": 0.5,
}


@dataclass(frozen=True)
class PickupIntent:
    intent_type: str
    reason_code: str
    resolved_date: _dt.date | None = None
    preferred_exact_time: _dt.time | None = None
    preferred_daypart: str | None = None
    lower_bound_time: _dt.time | None = None       # for "after six"
    same_day: bool = False
    immediate: bool = False
    valid: bool = True
    clarification_required: bool = False
    message: str | None = None                     # short human hint for the model

    def as_dict(self) -> dict:
        return {
            "intent_type": self.intent_type,
            "reason_code": self.reason_code,
            "resolved_date": self.resolved_date.isoformat() if self.resolved_date else None,
            "preferred_exact_time": (
                self.preferred_exact_time.strftime("%H:%M") if self.preferred_exact_time else None
            ),
            "preferred_daypart": self.preferred_daypart,
            "lower_bound_time": (
                self.lower_bound_time.strftime("%H:%M") if self.lower_bound_time else None
            ),
            "same_day": self.same_day,
            "immediate": self.immediate,
            "valid": self.valid,
            "clarification_required": self.clarification_required,
            "message": self.message,
        }


def _daypart_in(text: str) -> str | None:
    if "tonight" in text or "this evening" in text or "evening" in text:
        return "evening"
    if "afternoon" in text:
        return "afternoon"
    if "morning" in text:
        return "morning"
    if "night" in text:
        return "night"
    if "noon" in text or "midday" in text:
        return "afternoon"
    return None


def _hour_to_time(hour: int, minute: int, meridiem: str | None, daypart: str | None) -> _dt.time | None:
    """Best-effort 12h→24h. Uses explicit am/pm; otherwise business context:
    bare 1–7 → PM (we open 08:00), 8–11 → AM unless an evening/pm daypart, 12 → noon."""
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return None
    if meridiem == "am":
        h = 0 if hour == 12 else hour
    elif meridiem == "pm":
        h = 12 if hour == 12 else (hour + 12 if hour < 12 else hour)
    elif hour <= 7:
        h = hour + 12          # 1..7 with no am/pm → afternoon/evening
    elif hour in (8, 9, 10, 11):
        h = hour + 12 if daypart in ("evening", "night") else hour
    else:
        h = hour               # 12..23 as-is
    if h > 23:
        return None
    return _dt.time(h, minute)


def _parse_relative_delta(text: str) -> _dt.timedelta | None:
    """Parse 'in two hours', 'after an hour', 'in 90 minutes', 'after 2 hrs'."""
    m = re.search(r"\b(?:in|after)\s+(\d+|an?|one|two|three|four|five|six|seven|eight|nine|ten|half)\s*"
                  r"(hour|hours|hr|hrs|minute|minutes|min|mins)\b", text)
    if not m:
        return None
    qty_raw, unit = m.group(1), m.group(2)
    qty = float(qty_raw) if qty_raw.isdigit() else float(_NUM_WORDS.get(qty_raw, 0))
    if qty <= 0:
        return None
    if unit.startswith(("hour", "hr")):
        return _dt.timedelta(hours=qty)
    return _dt.timedelta(minutes=qty)


def _fmt_time_12h(t: _dt.time) -> str:
    """Portable 12-hour label ('11:30 AM') — %-I / %#I are platform-specific."""
    hour12 = t.hour % 12 or 12
    ampm = "AM" if t.hour < 12 else "PM"
    return f"{hour12}:{t.minute:02d} {ampm}"


def _parse_after_bound(text: str) -> _dt.time | None:
    """'after six' / 'after 6' / 'after 6pm' → an inclusive lower-bound time.
    Bare small hours bias to PM (business context), matching 'after six' = 18:00."""
    m = re.search(r"\bafter\s+(\d{1,2}|an?|one|two|three|four|five|six|seven|eight|nine|ten|"
                  r"eleven|twelve)\s*(am|pm|a\.m\.|p\.m\.)?\b", text)
    if not m:
        return None
    word = m.group(1)
    _word_hours = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
                   "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12}
    hour = int(word) if word.isdigit() else _word_hours.get(word)
    if hour is None:
        return None
    return _hour_to_time(hour, 0, _norm_meridiem(m.group(2)), _daypart_in(text))


def _parse_clock(text: str) -> tuple[int, int, str | None] | None:
    """Find an explicit clock time: '7', '7pm', '7:30', '11 30', 'around 5'.
    Returns (hour, minute, meridiem|None) or None. Avoids matching bare dates."""
    # H:MM or H.MM or "H MM" (with am/pm optional)
    m = re.search(r"\b(\d{1,2})\s*[:.\s]\s*(\d{2})\s*(am|pm|a\.m\.|p\.m\.)?\b", text)
    if m:
        return int(m.group(1)), int(m.group(2)), _norm_meridiem(m.group(3))
    # bare hour with am/pm, or "at/around/after H"
    m = re.search(r"\b(?:at|around|by|after|before)?\s*(\d{1,2})\s*(am|pm|a\.m\.|p\.m\.)\b", text)
    if m:
        return int(m.group(1)), 0, _norm_meridiem(m.group(2))
    m = re.search(r"\b(?:at|around|by)\s+(\d{1,2})\b", text)
    if m:
        return int(m.group(1)), 0, None
    return None


def _norm_meridiem(s: str | None) -> str | None:
    if not s:
        return None
    s = s.replace(".", "").lower()
    return "am" if s.startswith("a") else "pm"


def resolve(
    phrase: str,
    *,
    now: _dt.datetime,
    market: str | None = None,
    existing_date: _dt.date | None = None,
) -> PickupIntent:
    """Resolve a temporal pickup phrase against a timezone-aware ``now``.

    Returns ``intent_type == NONE`` (reason NOT_TEMPORAL) when the phrase carries
    no temporal signal we handle here, so the caller can fall back to the strict
    calendar date parser."""
    today = now.date()
    text = " " + re.sub(r"\s+", " ", (phrase or "").strip().lower()) + " "

    # --- Past date: yesterday / "day before" ---------------------------------
    if re.search(r"\byesterday\b", text) or re.search(r"\bday before\b", text):
        return PickupIntent(
            intent_type=INTENT_NONE, reason_code=REASON_PAST_DATE_INVALID,
            valid=False, clarification_required=True,
            message="A pickup can't be scheduled for a past date.",
        )

    daypart = _daypart_in(text)

    # --- Immediate / earliest ------------------------------------------------
    immediate_re = (r"\bnow\b|\bright now\b|\bimmediately\b|\bstraight ?away\b|"
                    r"send someone|come now|collect now|pick ?up now|pickup now")
    earliest_re = (r"\basap\b|as soon as possible|earliest( available)?|"
                   r"soonest|first available")
    if re.search(immediate_re, text):
        return PickupIntent(
            intent_type=INTENT_IMMEDIATE, reason_code=REASON_RESOLVED_TODAY,
            resolved_date=today, same_day=True, immediate=True,
            message="Earliest valid pickup today.",
        )
    if re.search(earliest_re, text):
        return PickupIntent(
            intent_type=INTENT_EARLIEST, reason_code=REASON_RESOLVED_TODAY,
            resolved_date=today, same_day=True, immediate=True,
            message="Earliest available pickup today.",
        )

    # --- Relative time ("in two hours", "after an hour") ---------------------
    delta = _parse_relative_delta(text)
    if delta is not None:
        target = now + delta
        same_day = target.date() == today
        return PickupIntent(
            intent_type=INTENT_RELATIVE_TIME, reason_code=REASON_RESOLVED_RELATIVE_TIME,
            resolved_date=target.date(), preferred_exact_time=target.timetz().replace(tzinfo=None),
            same_day=same_day,
            message=f"Around {target.strftime('%H:%M')} today." if same_day else None,
        )

    # --- Explicit relative dates --------------------------------------------
    resolved_date: _dt.date | None = None
    reason = REASON_RESOLVED_DATE
    if re.search(r"day after tomorrow|overmorrow", text):
        resolved_date, reason = today + _dt.timedelta(days=2), REASON_RESOLVED_DATE
    elif re.search(r"\btomorrow\b|\btmrw\b|\btmr\b", text):
        resolved_date, reason = today + _dt.timedelta(days=1), REASON_RESOLVED_TOMORROW
    elif re.search(r"\btoday\b|\blater today\b|\bthis (morning|afternoon|evening)\b|\btonight\b", text):
        resolved_date, reason = today, REASON_RESOLVED_TODAY
    else:
        wd = _named_weekday(text)
        if wd is not None:
            resolved_date = _next_weekday(today, wd, force_next="next " in text)
            reason = REASON_RESOLVED_WEEKDAY

    # --- Clock time within the (possibly resolved) date ----------------------
    preferred_time = None
    lower_bound = _parse_after_bound(text)          # "after six" → lower bound
    ambiguous = False
    if lower_bound is None:
        clock_hit = _parse_clock(text)
        if clock_hit:
            h, mnt, mer = clock_hit
            preferred_time = _hour_to_time(h, mnt, mer, daypart)
            if preferred_time is None:
                ambiguous = True

    date_for_time = resolved_date or existing_date

    # Past-time check when the time lands on today.
    if date_for_time == today and preferred_time is not None:
        candidate = _dt.datetime.combine(today, preferred_time, tzinfo=now.tzinfo)
        if candidate <= now:
            return PickupIntent(
                intent_type=INTENT_EXACT_TIME, reason_code=REASON_PAST_TIME_INVALID,
                resolved_date=today, preferred_exact_time=preferred_time, same_day=True,
                valid=False, clarification_required=True,
                message=f"{_fmt_time_12h(preferred_time)} has already passed today.",
            )

    # --- Assemble ------------------------------------------------------------
    if resolved_date is None and preferred_time is None and lower_bound is None and daypart is None:
        return PickupIntent(intent_type=INTENT_NONE, reason_code=REASON_NOT_TEMPORAL)

    same_day = (resolved_date or existing_date) == today
    if preferred_time is not None:
        intent = INTENT_EXACT_TIME
        if ambiguous:
            reason = REASON_AMBIGUOUS_TIME
    elif lower_bound is not None:
        intent = INTENT_TIME_RANGE
    elif daypart is not None:
        intent = INTENT_DAYPART
    elif resolved_date is not None and reason == REASON_RESOLVED_TODAY:
        intent = INTENT_FLEXIBLE_SAME_DAY
    else:
        intent = INTENT_DATE_ONLY

    return PickupIntent(
        intent_type=intent, reason_code=reason,
        resolved_date=resolved_date or existing_date,
        preferred_exact_time=preferred_time, preferred_daypart=daypart,
        lower_bound_time=lower_bound, same_day=bool(same_day),
        clarification_required=ambiguous,
    )


def _named_weekday(text: str) -> int | None:
    for word, idx in _WEEKDAYS.items():
        if re.search(rf"\b{word}\b", text):
            return idx
    return None


def _next_weekday(today: _dt.date, weekday: int, *, force_next: bool = False) -> _dt.date:
    """Nearest FUTURE occurrence of ``weekday`` (Mon=0). 'next <weekday>' when it
    is that same weekday today jumps a full week."""
    ahead = (weekday - today.weekday()) % 7
    if ahead == 0:
        ahead = 7                         # never resolve a weekday to today
    elif force_next and ahead < 7:
        pass                              # already the coming occurrence
    return today + _dt.timedelta(days=ahead)
