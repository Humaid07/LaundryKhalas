"""Group inbound fragments into logical turns using the PRODUCTION rules.

Production aggregates fragments per conversation with an adaptive inactivity
window: each fragment is classified (complete / short-fragment / structured) and
a debounce is chosen; fragments arriving within that window are combined into one
turn. We reproduce that grouping DECISION here against the historical timestamps
so we feed the agent the same combined turns it would have aggregated live —
without merging anything production would have kept separate.

We deliberately drive the webhook with aggregation OFF (one combined message per
group) so each turn maps to exactly one deterministic agent reply.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..core.models import Direction, MessageType, ParsedMessage


@dataclass
class TurnGroup:
    """One logical turn: the fragments the aggregator would combine."""

    fragments: list[ParsedMessage] = field(default_factory=list)

    @property
    def combined_text(self) -> str:
        parts = [ (m.text or m.caption or "").strip() for m in self.fragments ]
        return "\n".join(p for p in parts if p)

    @property
    def first(self) -> ParsedMessage:
        return self.fragments[0]

    @property
    def is_media(self) -> bool:
        return any(m.media_reference for m in self.fragments)

    @property
    def media_message(self) -> Optional[ParsedMessage]:
        for m in self.fragments:
            if m.media_reference:
                return m
        return None


# Debounce windows (seconds) mirroring settings defaults
# (debounce_short/standard/fragment). A large historical gap always splits.
_DEBOUNCE = {
    "complete": 1.0,      # a complete thought — short wait
    "structured": 1.0,    # interactive/location — process promptly
    "fragment": 3.0,      # a short fragment — wait longer to combine
}
# Absolute ceiling: no matter the classification, a gap beyond this splits turns.
_MAX_COMBINE_GAP_SECONDS = 8.0


def _classify(text: str, msg: ParsedMessage) -> str:
    """Local, no-LLM classification mirroring services.message_completeness."""
    if msg.media_reference or msg.location_data:
        return "structured"
    t = (text or "").strip()
    if not t:
        return "structured"
    # Explicit "that's all" style — complete.
    lowered = t.lower()
    if lowered in ("that's all", "thats all", "done", "ok", "okay", "yes", "no"):
        return "complete"
    # Ends with sentence punctuation or is reasonably long -> complete.
    if t.endswith((".", "?", "!")) or len(t.split()) >= 6:
        return "complete"
    return "fragment"


def group_turns(messages: list[ParsedMessage]) -> list[TurnGroup]:
    """Group only INBOUND_CUSTOMER (and inbound media) messages into turns.

    Non-inbound (staff/system/empty) messages act as boundaries: a staff reply
    between two customer messages always starts a new turn (the customer was
    answered), mirroring live behaviour.
    """
    groups: list[TurnGroup] = []
    current: Optional[TurnGroup] = None
    prev_inbound: Optional[ParsedMessage] = None

    for m in messages:
        if m.direction == Direction.EMPTY_MESSAGE:
            continue
        if m.direction != Direction.INBOUND_CUSTOMER:
            # Staff/system boundary closes the current turn.
            if current is not None:
                groups.append(current)
                current = None
                prev_inbound = None
            continue

        # Media inbound is always its own turn (routed through the media path).
        if m.media_reference:
            if current is not None:
                groups.append(current)
                current = None
            groups.append(TurnGroup(fragments=[m]))
            prev_inbound = None
            continue

        if current is None:
            current = TurnGroup(fragments=[m])
            prev_inbound = m
            continue

        # Decide whether m combines with the current group.
        gap = _MAX_COMBINE_GAP_SECONDS + 1
        if prev_inbound is not None and prev_inbound.timestamp and m.timestamp:
            gap = (m.timestamp - prev_inbound.timestamp).total_seconds()
        label = _classify(prev_inbound.text if prev_inbound else "", prev_inbound) if prev_inbound else "fragment"
        window = _DEBOUNCE.get(label, 3.0)
        prev_complete = label == "complete"

        if (not prev_complete) and 0 <= gap <= min(window, _MAX_COMBINE_GAP_SECONDS):
            current.fragments.append(m)
        else:
            groups.append(current)
            current = TurnGroup(fragments=[m])
        prev_inbound = m

    if current is not None:
        groups.append(current)
    return groups
