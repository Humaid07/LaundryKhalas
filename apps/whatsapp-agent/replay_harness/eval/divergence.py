"""Conversation-divergence detection.

A historical customer message may not logically answer what the CURRENT agent
just asked (the new agent may take a different path). We record the divergence
rather than modifying the customer message to fit, and continue the replay.
"""
from __future__ import annotations

import re
from typing import Optional

from ..core.models import Divergence, ReplayTurn

CUSTOMER_MESSAGE_DOES_NOT_ANSWER = "CUSTOMER_MESSAGE_DOES_NOT_ANSWER_CURRENT_AGENT_REQUEST"
AGENT_REPEATED_FIELD = "AGENT_REPEATED_ALREADY_PROVIDED_FIELD"
MEDIA_CONTEXT_MISSING = "MEDIA_CONTEXT_MISSING"
CURRENT_AGENT_ALREADY_COMPLETED = "CURRENT_AGENT_ALREADY_COMPLETED_ORDER"

# What the agent asked for -> tokens that would answer it.
_FIELD_PATTERNS: list[tuple[str, re.Pattern, re.Pattern]] = [
    (
        "location_pin",
        re.compile(r"\b(location pin|share your location|drop a pin|send.*pin|your pin)\b", re.I),
        re.compile(r"(pin|location|\d+\.\d+)", re.I),
    ),
    (
        "pickup_area",
        re.compile(r"\b(which area|your area|where.*pickup|pickup area|where are you)\b", re.I),
        re.compile(r"(marina|jbr|downtown|deira|jumeirah|business bay|area|building|tower|street|\bal\b)", re.I),
    ),
    (
        "name",
        re.compile(r"\b(your name|who.*speaking|may i.*name|can i (?:get|have) your name)\b", re.I),
        re.compile(r"^[A-Za-z][A-Za-z .'-]{1,30}$"),
    ),
    (
        "service",
        re.compile(r"\b(which service|what service|wash.*fold.*clean|type of service)\b", re.I),
        re.compile(r"(wash|fold|press|iron|clean|dry ?clean|carpet|curtain|shoe|alter|repair)", re.I),
    ),
    (
        "quantity",
        re.compile(r"\b(how many|number of items|how much.*items|quantity)\b", re.I),
        re.compile(r"(\d+|one|two|three|four|five|couple|few)", re.I),
    ),
]


def _agent_requested_field(reply: str) -> Optional[tuple[str, re.Pattern]]:
    if not reply or "?" not in reply:
        return None
    for field, ask_re, answer_re in _FIELD_PATTERNS:
        if ask_re.search(reply):
            return field, answer_re
    return None


def detect(prev_turn: Optional[ReplayTurn], turn: ReplayTurn) -> Optional[Divergence]:
    """Detect divergence between what the PREVIOUS agent reply asked for and what
    THIS customer message actually says."""
    if prev_turn is None or not prev_turn.agent_reply:
        # If the very first agent reply already completed/confirmed an order and
        # the customer keeps going, that's a different kind of divergence handled
        # at conversation level; nothing to compare here.
        return None

    requested = _agent_requested_field(prev_turn.agent_reply)
    if requested is None:
        return None
    field, answer_re = requested
    customer_msg = turn.customer_message or ""
    if not customer_msg.strip():
        return None
    if not answer_re.search(customer_msg.strip()):
        return Divergence(
            turn_index=turn.turn_index,
            divergence_type=CUSTOMER_MESSAGE_DOES_NOT_ANSWER,
            agent_requested_field=field,
            historical_customer_message=customer_msg[:200],
        )
    return None
