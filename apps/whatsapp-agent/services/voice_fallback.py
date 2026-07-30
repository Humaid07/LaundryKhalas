"""Unprocessable-voice-note escalation — a pure decision engine.

The system cannot transcribe audio. Behaviour:
  1. First unique unprocessable voice note  -> send ONE polite text-fallback ask.
  2. Second DISTINCT unprocessable voice note -> create a human-intervention case
     (reason REPEATED_UNPROCESSABLE_VOICE_MESSAGE), hand over, stop replying.
  3. Duplicate webhook of the same audio id  -> ignore (no count, no reply).
  4. Already escalated / human takeover active -> store only, never reply.

Counting is by UNIQUE Evolution message id and is persisted on the conversation
row, so a restart / redeploy / worker retry never resets it. The count resets on
a valid text message, on human resolve/reset, or a new conversation lifecycle.

This module holds NO I/O — the webhook passes in the current persisted state and
applies the returned decision. That makes every branch unit-testable without a DB.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

REPEATED_UNPROCESSABLE_VOICE_REASON = "REPEATED_UNPROCESSABLE_VOICE_MESSAGE"

# Escalation status stored in conversations.voice_escalation_status
STATUS_NONE = "none"
STATUS_FALLBACK_SENT = "fallback_sent"
STATUS_ESCALATED = "escalated"

FALLBACK_TEXT = (
    "Apologies — I’m not able to process voice notes or audio messages just yet. "
    "Could you please send your request as a text message instead? Thank you!"
)

HANDOVER_TEXT = (
    "I’m sorry, I’m still unable to process the audio. I’ve transferred this "
    "conversation to our Operations team so someone can assist you directly."
)


class VoiceAction(str, Enum):
    DUPLICATE_IGNORED = "duplicate_ignored"   # same audio id as last — no-op
    FIRST_FALLBACK = "first_fallback"         # send FALLBACK_TEXT, mark fallback_sent
    ESCALATE = "escalate"                     # create human intervention + HANDOVER_TEXT
    HOLD = "hold"                             # already escalated / in takeover — store only


@dataclass(frozen=True)
class VoiceState:
    """Durable voice-escalation state read from the conversation row."""
    count: int = 0
    last_message_id: str | None = None
    escalation_status: str = STATUS_NONE


@dataclass(frozen=True)
class VoiceDecision:
    action: VoiceAction
    reply_text: str | None
    new_count: int
    new_status: str
    new_last_message_id: str | None
    escalation_reason: str | None = None

    @property
    def should_reply(self) -> bool:
        return self.reply_text is not None

    @property
    def should_escalate(self) -> bool:
        return self.action == VoiceAction.ESCALATE


def decide_voice_message(
    state: VoiceState,
    *,
    audio_message_id: str | None,
    takeover_active: bool = False,
) -> VoiceDecision:
    """Decide what to do with one inbound unprocessable audio message.

    ``audio_message_id`` is the Evolution provider message id (``key.id``); it is
    the sole basis for de-duplication and counting.
    """
    # Already handed over (either flagged here or a live human takeover): store
    # the message, never generate an AI reply, never ask for text again.
    if takeover_active or state.escalation_status == STATUS_ESCALATED:
        return VoiceDecision(
            action=VoiceAction.HOLD,
            reply_text=None,
            new_count=state.count,
            new_status=STATUS_ESCALATED if state.escalation_status == STATUS_ESCALATED else state.escalation_status,
            new_last_message_id=state.last_message_id,
        )

    # Duplicate webhook delivery of the SAME audio id — idempotent no-op.
    if audio_message_id and audio_message_id == state.last_message_id:
        return VoiceDecision(
            action=VoiceAction.DUPLICATE_IGNORED,
            reply_text=None,
            new_count=state.count,
            new_status=state.escalation_status,
            new_last_message_id=state.last_message_id,
        )

    new_count = state.count + 1

    # Second (or later) DISTINCT voice note after we already asked for text.
    if new_count >= 2:
        return VoiceDecision(
            action=VoiceAction.ESCALATE,
            reply_text=HANDOVER_TEXT,
            new_count=new_count,
            new_status=STATUS_ESCALATED,
            new_last_message_id=audio_message_id,
            escalation_reason=REPEATED_UNPROCESSABLE_VOICE_REASON,
        )

    # First distinct voice note — one polite text-fallback ask.
    return VoiceDecision(
        action=VoiceAction.FIRST_FALLBACK,
        reply_text=FALLBACK_TEXT,
        new_count=new_count,
        new_status=STATUS_FALLBACK_SENT,
        new_last_message_id=audio_message_id,
    )


def reset_state() -> VoiceState:
    """Zeroed state — used on a valid text message, human resolve/reset, or a new
    conversation lifecycle."""
    return VoiceState(count=0, last_message_id=None, escalation_status=STATUS_NONE)
