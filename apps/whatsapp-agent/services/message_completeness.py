"""Fast, LOCAL, deterministic message-completeness classifier for adaptive
debounce timing (response-timing spec).

Customers send one thought as several quick WhatsApp fragments ("Hi" / "need
wash" / "tomorrow"), but they also send fully-complete messages ("How much is
shirt cleaning?"). A single fixed inactivity window makes complete messages feel
slow and can still split fragments. This module classifies the LATEST inbound
fragment so the caller can pick a per-conversation debounce delay:

    STRUCTURED_ACTION          -> shortest delay (a button/list/slot/location pin)
    URGENT_OPERATIONAL_ACTION  -> shortest delay (explicit confirm / cancel)
    COMPLETE                   -> standard delay (a clearly complete message)
    LIKELY_COMPLETE            -> standard delay (a reasonable sentence)
    LIKELY_FRAGMENT            -> long fragment delay (likely followed by more)

It is intentionally cheap + rule-based: NO LLM call is made to decide how long to
wait (that would add the very latency + cost we are trying to cut). It never
touches the DB and never mutates state — pure text/flag → label.
"""
from __future__ import annotations

import re
from enum import Enum


class Completeness(str, Enum):
    STRUCTURED_ACTION = "STRUCTURED_ACTION"
    URGENT_OPERATIONAL_ACTION = "URGENT_OPERATIONAL_ACTION"
    COMPLETE = "COMPLETE"
    LIKELY_COMPLETE = "LIKELY_COMPLETE"
    LIKELY_FRAGMENT = "LIKELY_FRAGMENT"


# Debounce TIER each label maps to (resolved to milliseconds by settings). Kept
# here so the label→tier policy lives in ONE place; the actual durations are
# centralised in settings (never hardcoded across files).
DEBOUNCE_TIER: dict[Completeness, str] = {
    Completeness.STRUCTURED_ACTION: "short",
    Completeness.URGENT_OPERATIONAL_ACTION: "short",
    Completeness.COMPLETE: "standard",
    Completeness.LIKELY_COMPLETE: "standard",
    Completeness.LIKELY_FRAGMENT: "fragment",
}

# Selection ids that are an explicit confirm/cancel (urgent operational action).
_CONFIRM_SELECTIONS = {"confirm_booking"}
_CANCEL_SELECTIONS = {"cancel_booking"}

_CONFIRM_RE = re.compile(
    r"\b(confirm|go ahead|place (the )?order|book it|proceed with the order|"
    r"yes,? ?(please )?confirm|confirmed)\b")
_CANCEL_RE = re.compile(r"\b(cancel|stop the order|call it off)\b")
_PRICE_RE = re.compile(r"\b(how much|price|prices|cost|costs|rate|rates|charge|quote|per (kg|sqm|piece|item))\b")
_EDIT_RE = re.compile(r"\b(change|update|reschedule|move|switch|instead of|make it|set (the|it))\b")
_QUESTION_RE = re.compile(r"\b(how|what|when|where|can you|could you|do you|is it|are you|when can|what time)\b")
_TIME_RE = re.compile(r"\b(\d{1,2}\s?(am|pm)|\d{1,2}:\d{2}|noon|midnight|today|tonight|tomorrow|"
                      r"morning|afternoon|evening|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b")
_NUMBER_WORD_RE = re.compile(r"\b(one|two|three|four|five|six|seven|eight|nine|ten|dozen|\d+)\b")
_SERVICE_HINT_RE = re.compile(
    r"\b(shirt|shirts|trouser|trousers|suit|dress|abaya|kandura|carpet|rug|curtain|"
    r"sofa|laundry|wash|fold|press|pressing|clean|cleaning|dry ?clean|iron|ironing|"
    r"bedsheet|blanket|duvet|jacket|coat|shoe|shoes|bag)\b")

# All-continuation / greeting-only fragments are near-certain to be followed by more.
_GREETINGS = {"hi", "hii", "hiii", "hello", "helo", "hey", "heyy", "yo", "salam",
              "assalam", "assalamualaikum", "hala", "marhaba", "good morning",
              "good evening", "good afternoon", "gm", "ge"}
_CONTINUATION_LEADERS = {"after", "before", "from", "at", "on", "by", "around",
                         "near", "and", "also", "plus", "then", "with", "for", "to"}
_CONTINUATION_WORDS = {"tomorrow", "today", "tonight", "morning", "evening",
                       "afternoon", "asap", "ok", "okay", "yes", "yeah", "no",
                       "please", "thanks", "thankyou", "sure", "and", "also"}
_DANGLING_ENDINGS = {"and", "or", "but", "with", "to", "for", "from", "the", "a",
                     "an", "of", "at", "on", "in", "my", "i", "is", "are", "need"}


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def classify(text: str | None, *, selection_id: str | None = None,
             has_location: bool = False, answers_requested_field: bool = False) -> Completeness:
    """Classify the latest inbound fragment. Deterministic + side-effect free.

    ``selection_id``/``has_location`` come from a structured WhatsApp interaction
    (list/button/slot selection or a location pin). ``answers_requested_field`` is
    True when the message plausibly answers the exact field the agent just asked
    for (so a short 'tomorrow' after "which day?" is treated as COMPLETE, not a
    stray fragment)."""
    # 1) Structured interactions are complete actions.
    if selection_id:
        if selection_id in _CANCEL_SELECTIONS or selection_id in _CONFIRM_SELECTIONS:
            return Completeness.URGENT_OPERATIONAL_ACTION
        return Completeness.STRUCTURED_ACTION
    if has_location:
        return Completeness.STRUCTURED_ACTION

    raw = (text or "").strip()
    if not raw:
        return Completeness.LIKELY_FRAGMENT
    low = raw.lower()
    words = _words(raw)
    n = len(words)

    # 2) Explicit confirm / cancel → urgent operational action (minimal wait).
    if _CANCEL_RE.search(low) or (_CONFIRM_RE.search(low) and n <= 8):
        return Completeness.URGENT_OPERATIONAL_ACTION

    # 3) A message that answers the exact requested field is complete in context.
    if answers_requested_field:
        return Completeness.COMPLETE

    # 4) Strong completeness signals.
    has_q = "?" in raw
    if has_q or _PRICE_RE.search(low):
        return Completeness.COMPLETE
    # order-edit instruction WITH a concrete value ("change pickup time to 8 PM")
    if _EDIT_RE.search(low) and (re.search(r"\d", low) or _TIME_RE.search(low)):
        return Completeness.COMPLETE
    # multi-field natural sentence: a service + a quantity/date/time in one message
    signals = sum(bool(rx.search(low)) for rx in (_SERVICE_HINT_RE, _NUMBER_WORD_RE, _TIME_RE))
    if n >= 6 and signals >= 2:
        return Completeness.COMPLETE

    # 5) Fragment signals (likely followed by more).
    if low in _GREETINGS or all(w in _GREETINGS for w in words):
        return Completeness.LIKELY_FRAGMENT
    if words and words[-1] in _DANGLING_ENDINGS:
        return Completeness.LIKELY_FRAGMENT
    if n <= 3:
        # short continuation ("tomorrow", "after six", "from marina", "and pressed")
        if words[0] in _CONTINUATION_LEADERS or all(w in _CONTINUATION_WORDS for w in words):
            return Completeness.LIKELY_FRAGMENT
        # a short line with no question / number / time and no service detail
        if not (re.search(r"\d", low) or _TIME_RE.search(low)):
            return Completeness.LIKELY_FRAGMENT

    # 6) A reasonable sentence with no strong signal → standard wait.
    return Completeness.LIKELY_COMPLETE


def debounce_seconds(label: Completeness, *, short_s: float, standard_s: float,
                     fragment_s: float) -> float:
    """Resolve a classification to a debounce delay (seconds) using the caller's
    centralised tier durations."""
    tier = DEBOUNCE_TIER[label]
    return {"short": short_s, "standard": standard_s, "fragment": fragment_s}[tier]
