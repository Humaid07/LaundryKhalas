"""Inbound-media classification for WhatsApp (Evolution) messages.

The agent must know *what kind* of message arrived BEFORE any of it reaches
Claude, so it never pretends to have understood audio it cannot transcribe. This
module is a pure classifier over the raw Evolution `message` object (the value of
`messages.upsert -> data.message`); it performs no I/O and invents nothing.

The system has no speech-to-text provider, so AUDIO is explicitly "unprocessable"
today — the caller routes it to the text-fallback / human-intervention path
(see services.voice_fallback), never to the LLM.
"""

from __future__ import annotations

from enum import Enum


class MediaKind(str, Enum):
    TEXT = "text"
    INTERACTIVE = "interactive"  # list/button reply — treated as text-equivalent
    AUDIO = "audio"  # voice note / ptt / audio attachment — UNPROCESSABLE today
    IMAGE = "image"
    VIDEO = "video"
    DOCUMENT = "document"
    LOCATION = "location"
    STICKER = "sticker"
    CONTACT = "contact"
    REACTION = "reaction"
    EMPTY = "empty"
    UNKNOWN = "unknown"


# Evolution/Baileys audio shapes. A WhatsApp voice note is `audioMessage` with
# `ptt: true`; a shared audio file is `audioMessage` with `ptt` absent/false.
_AUDIO_KEYS = ("audioMessage", "pttMessage", "voiceMessage")
_TEXT_KEYS = ("conversation", "extendedTextMessage")
_INTERACTIVE_KEYS = (
    "listResponseMessage",
    "buttonsResponseMessage",
    "templateButtonReplyMessage",
)
_LOCATION_KEYS = ("locationMessage", "liveLocationMessage")


def _unwrap(message: dict) -> dict:
    """Unwrap ephemeral / view-once / edited envelopes to the inner message."""
    seen = 0
    cur = message
    while isinstance(cur, dict) and seen < 4:
        for wrapper in ("ephemeralMessage", "viewOnceMessage", "viewOnceMessageV2", "documentWithCaptionMessage", "editedMessage"):
            inner = cur.get(wrapper)
            if isinstance(inner, dict) and isinstance(inner.get("message"), dict):
                cur = inner["message"]
                break
        else:
            break
        seen += 1
    return cur if isinstance(cur, dict) else {}


def classify_inbound_media(message: dict | None) -> MediaKind:
    """Return the :class:`MediaKind` of a raw Evolution message object.

    Pure and defensive: an unknown / missing shape yields UNKNOWN or EMPTY, never
    an exception. AUDIO is detected regardless of caption so a voice note can
    never be mistaken for text.
    """
    if not isinstance(message, dict) or not message:
        return MediaKind.EMPTY
    msg = _unwrap(message)

    # Audio first — must win even if some client attaches other envelopes.
    if any(isinstance(msg.get(k), dict) for k in _AUDIO_KEYS):
        return MediaKind.AUDIO
    if isinstance(msg.get("locationMessage"), dict) or isinstance(msg.get("liveLocationMessage"), dict):
        return MediaKind.LOCATION
    if any(isinstance(msg.get(k), (dict, str)) and msg.get(k) not in (None, "") for k in _INTERACTIVE_KEYS):
        return MediaKind.INTERACTIVE
    if isinstance(msg.get("conversation"), str) and msg["conversation"].strip():
        return MediaKind.TEXT
    ext = msg.get("extendedTextMessage")
    if isinstance(ext, dict) and isinstance(ext.get("text"), str) and ext["text"].strip():
        return MediaKind.TEXT
    if isinstance(msg.get("imageMessage"), dict):
        return MediaKind.IMAGE
    if isinstance(msg.get("videoMessage"), dict):
        return MediaKind.VIDEO
    if isinstance(msg.get("documentMessage"), dict):
        return MediaKind.DOCUMENT
    if isinstance(msg.get("stickerMessage"), dict):
        return MediaKind.STICKER
    if isinstance(msg.get("contactMessage"), dict) or isinstance(msg.get("contactsArrayMessage"), dict):
        return MediaKind.CONTACT
    if isinstance(msg.get("reactionMessage"), dict):
        return MediaKind.REACTION
    return MediaKind.UNKNOWN


def is_unprocessable_audio(kind: MediaKind) -> bool:
    """Audio has no transcription path today, so it is unprocessable."""
    return kind == MediaKind.AUDIO
