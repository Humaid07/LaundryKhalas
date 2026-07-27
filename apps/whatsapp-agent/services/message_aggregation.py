"""Pure logic for aggregating rapid inbound WhatsApp fragments into ONE logical
customer turn (task spec §§14-23).

Customers often send one thought as several quick messages ("Hi" / "need wash" /
"tomorrow"). This module holds the DECISION + COMBINE logic with NO I/O, so it is
fully unit-testable; the durable buffer, debounce timer, per-conversation lock
and DB writes live in ``services.turn_service`` / the webhook.

Two concerns:
  * ``combine_fragments`` — merge stored fragments (chronological) into one
    logical turn input, preserving meaningful boundaries and carrying the latest
    interactive selection / shared location (spec §19).
  * ``flush_decision`` — given the turn's first/last fragment times and now,
    decide whether the aggregation window has closed: ~debounce seconds of
    inactivity after the latest fragment, but never longer than the max window
    from the first fragment (spec §§15-16). An explicit "that's all" closes it
    early (spec §23).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

# Optional explicit-completion hints (spec §23). These are HINTS only — a
# customer never has to send them; they just let us close the window early.
_EXPLICIT_SEND_PHRASES = (
    "that's all", "thats all", "that is all", "please confirm", "confirm order",
    "confirm my order", "confirm the order", "confirm booking", "confirm the booking",
    "go ahead", "done", "that's it", "thats it", "that's everything", "nothing else",
    "book it", "place the order", "place my order",
)


def is_explicit_send(text: str | None) -> bool:
    """True when the customer clearly signalled they are finished for this turn
    (an optional early-close hint, spec §23). Deliberately conservative so we
    never cut a turn short on an ambiguous message."""
    if not text:
        return False
    # Normalise: lowercase and strip punctuation so "That's all." / "Done!" match.
    cleaned = "".join(ch if ch.isalnum() or ch == "'" else " " for ch in text.lower())
    low = f" {' '.join(cleaned.split())} "
    return any(f" {p} " in low for p in _EXPLICIT_SEND_PHRASES)


@dataclass
class CombinedTurn:
    """The single logical input produced from a turn's buffered fragments."""
    text: str                              # newline-joined text fragments (chronological)
    message_count: int
    selection_id: str | None = None        # latest interactive list/button selection
    latitude: float | None = None          # latest shared location
    longitude: float | None = None
    has_location: bool = False
    fragments: list[str] = field(default_factory=list)  # individual texts, for audit/LLM


def combine_fragments(fragments: list[dict]) -> CombinedTurn:
    """Combine buffered fragments (already in chronological order) into ONE turn.

    Each fragment dict may carry ``text``, ``selection_id``, ``latitude`` and
    ``longitude`` (the shapes ``parse_evolution_webhook`` produces). Text parts
    are newline-joined preserving order (spec §19 — never concatenated in a way
    that changes meaning); the LATEST interactive selection and the LATEST shared
    location win, since they represent the customer's most recent concrete action.
    """
    text_parts: list[str] = []
    selection_id: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    has_location = False
    for f in fragments:
        t = (f.get("text") or "").strip()
        if t:
            text_parts.append(t)
        if f.get("selection_id"):
            selection_id = f["selection_id"]
        if f.get("latitude") is not None and f.get("longitude") is not None:
            latitude, longitude, has_location = f["latitude"], f["longitude"], True
    return CombinedTurn(
        text="\n".join(text_parts),
        message_count=len(fragments),
        selection_id=selection_id,
        latitude=latitude,
        longitude=longitude,
        has_location=has_location,
        fragments=text_parts,
    )


@dataclass
class FlushDecision:
    should_flush: bool
    reason: str                 # inactivity | max_window | explicit | interactive | not_ready
    wait_seconds: float = 0.0   # when not flushing, how long until the next check


def flush_decision(
    first_message_at: datetime,
    last_message_at: datetime,
    now: datetime,
    *,
    debounce_seconds: float,
    max_seconds: float,
    explicit_send: bool = False,
    interactive_only: bool = False,
) -> FlushDecision:
    """Decide whether a turn's aggregation window has closed.

    Closes when: an explicit "that's all" hint was sent (spec §23); OR the turn
    is a single complete interactive selection (may be processed faster, spec
    §16); OR the max window from the first fragment elapsed (spec §15 hard cap);
    OR debounce seconds of inactivity elapsed since the last fragment (spec §15).
    Otherwise returns the seconds to wait before re-checking.
    """
    if explicit_send:
        return FlushDecision(True, "explicit")
    if interactive_only:
        return FlushDecision(True, "interactive")

    since_last = (now - last_message_at).total_seconds()
    since_first = (now - first_message_at).total_seconds()

    if since_first >= max_seconds:
        return FlushDecision(True, "max_window")
    if since_last >= debounce_seconds:
        return FlushDecision(True, "inactivity")

    # Not ready yet — wait until whichever deadline comes first.
    wait = min(debounce_seconds - since_last, max_seconds - since_first)
    return FlushDecision(False, "not_ready", wait_seconds=max(0.0, wait))


def deadlines(first_message_at: datetime, last_message_at: datetime, *,
              debounce_seconds: float, max_seconds: float) -> datetime:
    """The absolute time this turn must be processed by: the earlier of the
    debounce deadline (last + debounce) and the hard cap (first + max)."""
    debounce_deadline = last_message_at + timedelta(seconds=debounce_seconds)
    hard_cap = first_message_at + timedelta(seconds=max_seconds)
    return min(debounce_deadline, hard_cap)
