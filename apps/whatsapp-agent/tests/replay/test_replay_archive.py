"""Tests for the replay-harness archive layer: HTML parsing, classification,
exact-text preservation, timestamps, media mapping, fingerprint & dedup."""
from __future__ import annotations

from datetime import datetime

from replay_harness.archive.html_parser import parse_html, resolve_media_availability
from replay_harness.archive.fingerprint import (
    compute_fingerprint,
    customer_hash,
    dedupe,
)
from replay_harness.core.models import Conversation, Direction, MessageType, MEDIA_BINARY_UNAVAILABLE
from tests.replay.fixtures_html import CONV_HTML, CONV_HTML_DUP


def _parse(html: str, chat_id="+44 7519 510517"):
    return parse_html(html, source_chat_id=chat_id, source_filename=f"{chat_id}/{chat_id}.html")


def test_direction_detection():
    msgs = _parse(CONV_HTML)
    inbound = [m for m in msgs if m.direction == Direction.INBOUND_CUSTOMER]
    outbound = [m for m in msgs if m.direction == Direction.OUTBOUND_HISTORICAL_STAFF]
    # 4 inbound (2 text, 1 audio, 1 image) — the empty one is EMPTY_MESSAGE.
    assert len(inbound) == 4
    assert len(outbound) == 2  # "we dont do repairs" + price list (encryption line is SYSTEM)


def test_system_and_empty_excluded_from_inbound():
    msgs = _parse(CONV_HTML)
    assert any(m.direction == Direction.SYSTEM_EVENT for m in msgs)
    assert any(m.direction == Direction.EMPTY_MESSAGE for m in msgs)
    # System/empty are never INBOUND_CUSTOMER.
    for m in msgs:
        if m.direction in (Direction.SYSTEM_EVENT, Direction.EMPTY_MESSAGE):
            assert m.direction != Direction.INBOUND_CUSTOMER


def test_exact_text_preserved():
    msgs = _parse(CONV_HTML)
    texts = [m.text for m in msgs if m.direction == Direction.INBOUND_CUSTOMER]
    # Typos, punctuation, capitalization preserved verbatim.
    assert "how much this" in texts
    assert "best price??" in texts


def test_timestamps_parsed_dd_mm_yyyy():
    msgs = _parse(CONV_HTML)
    first = next(m for m in msgs if m.source_message_id == "AAAA1111")
    assert first.timestamp == datetime(2026, 5, 29, 14, 43)


def test_audio_message_detected():
    msgs = _parse(CONV_HTML)
    audio = next(m for m in msgs if m.source_message_id == "CCCC1111")
    assert audio.message_type == MessageType.AUDIO
    assert audio.media_reference == "2026_05_29_150500_CCCC1111.oga"
    assert audio.direction == Direction.INBOUND_CUSTOMER


def test_image_with_caption():
    msgs = _parse(CONV_HTML)
    img = next(m for m in msgs if m.source_message_id == "DDDD1111")
    assert img.message_type == MessageType.IMAGE
    assert img.media_reference.endswith(".jpeg")
    # Caption text preserved (incl. emoji).
    assert "need repair on this" in img.caption


def test_inline_emoji_img_not_treated_as_media():
    msgs = _parse(CONV_HTML)
    price = next(m for m in msgs if m.source_message_id == "EEEE1111")
    # The ../imgs/emoji/basket.png must NOT become a media message.
    assert price.message_type == MessageType.TEXT
    assert price.media_reference is None
    # Emoji alt lifted into text.
    assert "🧺" in price.text


def test_media_availability_flag():
    msgs = _parse(CONV_HTML)
    # Only the audio binary is present; the image binary is missing.
    resolve_media_availability(msgs, available_basenames={"2026_05_29_150500_CCCC1111.oga"})
    audio = next(m for m in msgs if m.source_message_id == "CCCC1111")
    img = next(m for m in msgs if m.source_message_id == "DDDD1111")
    assert audio.media_available is True
    assert img.media_available is False
    assert MEDIA_BINARY_UNAVAILABLE in img.caption


def test_customer_hash_is_one_way_and_stable():
    h1 = customer_hash("+44 7519 510517")
    h2 = customer_hash("+44 7519 510517")
    h3 = customer_hash("+44 7519 510518")
    assert h1 == h2 and h1 != h3
    # Not reversible: hash contains none of the original digits.
    assert "7519" not in h1


def _conv_from_html(html, chat_id, archive):
    msgs = parse_html(html, source_chat_id=chat_id, source_filename=f"{chat_id}.html")
    c = Conversation(
        source_archive=archive,
        source_chat_id=chat_id,
        source_filename=f"{chat_id}.html",
        customer_identifier_hash=customer_hash(chat_id),
        messages=msgs,
    )
    c.fingerprint = compute_fingerprint(c)
    return c


def test_fingerprint_matches_duplicate():
    a = _conv_from_html(CONV_HTML, "+44 7519 510517", "WhatsApp_All_Chats.zip")
    b = _conv_from_html(CONV_HTML_DUP, "+44 7519 510517", "chats_html.zip")
    assert a.fingerprint == b.fingerprint


def test_dedupe_prefers_primary_archive():
    a = _conv_from_html(CONV_HTML, "+44 7519 510517", "WhatsApp_All_Chats.zip")
    b = _conv_from_html(CONV_HTML_DUP, "+44 7519 510517", "chats_html.zip")
    kept, dupes = dedupe([b, a])  # fallback listed first on purpose
    kept_ids = [c.source_archive for c in kept]
    assert kept_ids == ["WhatsApp_All_Chats.zip"]
    assert len(dupes) == 1
    assert dupes[0].excluded_archive == "chats_html.zip"
    assert "primary" in dupes[0].reason


def test_distinct_customers_not_deduped():
    a = _conv_from_html(CONV_HTML, "+44 7519 510517", "WhatsApp_All_Chats.zip")
    b = _conv_from_html(CONV_HTML, "+91 98806 94426", "WhatsApp_All_Chats.zip")
    kept, dupes = dedupe([a, b])
    assert len(kept) == 2
    assert len(dupes) == 0
