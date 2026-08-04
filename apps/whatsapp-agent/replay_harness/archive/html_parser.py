"""Parser for WhatsApp HTML chat exports (the format inside WhatsApp_All_Chats.zip).

Format (obfuscated but stable class names):
  - Each message is a `<div class="__vW7d1 ..." id=<MSGID>>` block.
  - Direction: inner div carries `__message-in` (customer) or `__message-out` (staff).
  - Text: `<span dir=... class="__selectable-text __invisible-space __copyable-text">TEXT</span>`
    (emojis are literal unicode; `<br>` = newline).
  - Timestamp: time-only span `<span class="___3EFt_">HH:MM</span>`.
  - Date separators: a `__vW7d1` block WITHOUT direction, containing a date span
    (class `__Zq3Mc`) like `26/07/2026` (DD/MM/YYYY). Applies to following messages.
  - Media: `<audio ... src="X.oga">`, `<img ... src="X.jpeg">`, video/doc similar.
  - Location / contact appear as special blocks (best-effort).

Text is decoded as UTF-8 and preserved EXACTLY (typos, punctuation, casing,
mixed-language, repeated messages, fragments). We only turn `<br>` into `\n`,
lift emoji `<img alt>` to their alt text, strip remaining tags, and html.unescape.
"""
from __future__ import annotations

import html
import re
from datetime import datetime
from typing import Optional

from ..core.models import Direction, MessageType, ParsedMessage, MEDIA_BINARY_UNAVAILABLE

# --- regexes over the stable markup ---------------------------------------
# Split the document into top-level message blocks. Each starts with the
# __vW7d1 wrapper. We capture up to the next wrapper.
_BLOCK_RE = re.compile(
    r'<div\s+class="__vW7d1[^"]*"(?P<attrs>[^>]*)>(?P<body>.*?)(?=<div\s+class="__vW7d1|</body>|\Z)',
    re.DOTALL,
)
_ID_RE = re.compile(r'\bid=([A-Za-z0-9]+)')
_MSG_IN_RE = re.compile(r'__message-in\b')
_MSG_OUT_RE = re.compile(r'__message-out\b')
_TEXT_SPAN_RE = re.compile(
    r'class="__selectable-text[^"]*"[^>]*>(?P<txt>.*?)</span>', re.DOTALL
)
_TIME_RE = re.compile(r'class="___3EFt_">(?P<t>[0-9]{1,2}:[0-9]{2})(?:\s*(?P<ampm>[APap][Mm]))?</span>')
_DATE_SPAN_RE = re.compile(
    r'class="[^"]*__Zq3Mc[^"]*"[^>]*>\s*<span[^>]*>(?P<d>[^<]+)</span>'
)
_AUDIO_RE = re.compile(r'<audio[^>]*\ssrc="(?P<src>[^"]+)"')
_IMG_MEDIA_RE = re.compile(r'<img[^>]*\ssrc="(?P<src>[^"]+\.(?:jpe?g|png|webp|gif))"', re.IGNORECASE)
_VIDEO_RE = re.compile(r'<(?:video|source)[^>]*\ssrc="(?P<src>[^"]+\.(?:mp4|3gp|mov))"', re.IGNORECASE)
_DOC_RE = re.compile(r'\bhref="(?P<src>[^"]+\.(?:pdf|docx?|xlsx?|zip))"', re.IGNORECASE)


def _is_real_attachment(src: str) -> bool:
    """Reject inline emoji/asset sprites (e.g. ../imgs/emoji/X.png, css/emoji/...).

    Real WhatsApp media are same-folder, timestamp-named files with no path
    separator (e.g. 2026_07_11_150119_AC....jpeg).
    """
    if not src:
        return False
    low = src.lower()
    if "emoji" in low or low.startswith("../") or low.startswith("css/") or low.startswith("http"):
        return False
    return "/" not in src
_BR_RE = re.compile(r'<br\s*/?>', re.IGNORECASE)
_EMOJI_IMG_RE = re.compile(r'<img[^>]*\balt="(?P<alt>[^"]*)"[^>]*>')
_TAG_RE = re.compile(r'<[^>]+>')
# WhatsApp system lines that are not real messages.
_SYSTEM_MARKERS = (
    "Messages and calls are end-to-end encrypted",
    "end-to-end encryption",
    "This message was deleted",
    "You deleted this message",
    "Missed voice call",
    "Missed video call",
    "changed their phone number",
    "changed the group",
    "created group",
    "added you",
    "left",
    "security code changed",
)


def _clean_text(inner_html: str) -> str:
    """Turn a text span's inner HTML into exact plain text."""
    s = _BR_RE.sub("\n", inner_html)
    s = _EMOJI_IMG_RE.sub(lambda m: m.group("alt"), s)
    s = _TAG_RE.sub("", s)
    s = html.unescape(s)
    return s


def _parse_date(text: str) -> Optional[tuple[int, int, int]]:
    """Parse a date-separator label into (year, month, day)."""
    text = text.strip()
    m = re.match(r'(\d{1,2})/(\d{1,2})/(\d{2,4})', text)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y < 100:
            y += 2000
        # Export uses DD/MM/YYYY.
        return y, mo, d
    return None


def _parse_time(t: str, ampm: Optional[str]) -> Optional[tuple[int, int]]:
    try:
        hh, mm = t.split(":")
        h, m = int(hh), int(mm)
    except ValueError:
        return None
    if ampm:
        ap = ampm.lower()
        if ap == "pm" and h < 12:
            h += 12
        elif ap == "am" and h == 12:
            h = 0
    return h, m


def parse_html(
    content: str,
    *,
    source_chat_id: str,
    source_filename: str,
    sender_identifier_hash: str = "",
) -> list[ParsedMessage]:
    """Parse a WhatsApp HTML export into ordered ParsedMessage objects."""
    messages: list[ParsedMessage] = []
    current_date: Optional[tuple[int, int, int]] = None

    for block in _BLOCK_RE.finditer(content):
        attrs = block.group("attrs") or ""
        body = block.group("body") or ""
        combined = attrs + body

        # Date separator?
        dm = _DATE_SPAN_RE.search(combined)
        if dm and not (_MSG_IN_RE.search(combined) or _MSG_OUT_RE.search(combined)):
            parsed = _parse_date(dm.group("d"))
            if parsed:
                current_date = parsed
            continue

        is_in = bool(_MSG_IN_RE.search(combined))
        is_out = bool(_MSG_OUT_RE.search(combined))
        if not (is_in or is_out):
            # Structural/system block with no direction — skip unless it has text.
            continue

        id_m = _ID_RE.search(attrs)
        msg_id = id_m.group(1) if id_m else ""

        # Timestamp
        tm = _TIME_RE.search(body)
        ts: Optional[datetime] = None
        if tm and current_date:
            hm = _parse_time(tm.group("t"), tm.group("ampm"))
            if hm:
                y, mo, d = current_date
                try:
                    ts = datetime(y, mo, d, hm[0], hm[1])
                except ValueError:
                    ts = None

        # Text (may be caption for media)
        text_parts = [
            _clean_text(m.group("txt")) for m in _TEXT_SPAN_RE.finditer(body)
        ]
        text = "\n".join(p for p in text_parts if p).strip()

        # Media
        media_ref: Optional[str] = None
        mtype = MessageType.TEXT
        am = _AUDIO_RE.search(body)
        im = _IMG_MEDIA_RE.search(body)
        vm = _VIDEO_RE.search(body)
        do = _DOC_RE.search(body)
        if am and _is_real_attachment(am.group("src")):
            media_ref, mtype = am.group("src"), MessageType.AUDIO
        elif vm and _is_real_attachment(vm.group("src")):
            media_ref, mtype = vm.group("src"), MessageType.VIDEO
        elif im and _is_real_attachment(im.group("src")):
            media_ref, mtype = im.group("src"), MessageType.IMAGE
        elif do and _is_real_attachment(do.group("src")):
            media_ref, mtype = do.group("src"), MessageType.DOCUMENT

        direction = Direction.INBOUND_CUSTOMER if is_in else Direction.OUTBOUND_HISTORICAL_STAFF

        # System / encryption notice lines → SYSTEM_EVENT
        if text and any(mk.lower() in text.lower() for mk in _SYSTEM_MARKERS):
            messages.append(
                ParsedMessage(
                    source_chat_id=source_chat_id,
                    source_filename=source_filename,
                    source_message_id=msg_id,
                    direction=Direction.SYSTEM_EVENT,
                    message_type=MessageType.SYSTEM,
                    text=text,
                    timestamp=ts,
                    sender_identifier_hash=sender_identifier_hash if is_in else "",
                )
            )
            continue

        caption = ""
        if media_ref is not None:
            caption = text
            text = ""
            # If direction is inbound and media, keep it INBOUND_CUSTOMER but flag
            # message_type so the runner routes it through the media path.
        elif not text:
            # Empty inbound/outbound with no media/text.
            messages.append(
                ParsedMessage(
                    source_chat_id=source_chat_id,
                    source_filename=source_filename,
                    source_message_id=msg_id,
                    direction=Direction.EMPTY_MESSAGE,
                    message_type=MessageType.UNKNOWN,
                    timestamp=ts,
                    sender_identifier_hash=sender_identifier_hash if is_in else "",
                )
            )
            continue

        messages.append(
            ParsedMessage(
                source_chat_id=source_chat_id,
                source_filename=source_filename,
                source_message_id=msg_id,
                direction=direction,
                message_type=mtype,
                text=text,
                caption=caption,
                timestamp=ts,
                sender_identifier_hash=sender_identifier_hash if is_in else "",
                media_reference=media_ref,
            )
        )

    return messages


def resolve_media_availability(
    messages: list[ParsedMessage],
    *,
    available_basenames: set[str],
) -> None:
    """Mark media messages whose binary is missing from the archive."""
    for m in messages:
        if not m.media_reference:
            continue
        base = m.media_reference.rsplit("/", 1)[-1]
        if base not in available_basenames:
            m.media_available = False
            m.caption = (m.caption + f" [{MEDIA_BINARY_UNAVAILABLE}]").strip()
