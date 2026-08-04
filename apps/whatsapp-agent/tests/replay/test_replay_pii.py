"""Tests for PII redaction in reports."""
from __future__ import annotations

from replay_harness.core.pii import redact_location, redact_phone, redact_text


def test_redact_unit_and_building():
    out = redact_text("Apartment 1204, Marina Heights, Dubai Marina")
    assert "1204" not in out
    assert "[UNIT]" in out
    assert "Dubai Marina" in out  # area retained


def test_redact_phone_number():
    out = redact_text("call me on +971 50 123 4567 please")
    assert "1234567" not in out.replace(" ", "")
    assert "[PHONE]" in out


def test_redact_email():
    out = redact_text("email me at jon.doe@example.com")
    assert "jon.doe@example.com" not in out
    assert "[EMAIL]" in out


def test_redact_coordinates():
    out = redact_text("here is my pin 25.0805, 55.1403")
    assert "25.0805" not in out
    assert "[COORDS]" in out


def test_redact_iban_payment_ref():
    out = redact_text("paid via IBAN AE070331234567890123456")
    assert "AE070331234567890123456" not in out
    assert "[PAYMENT_REF]" in out


def test_redact_floor():
    out = redact_text("I'm on the 12th floor")
    assert "12th floor" not in out
    assert "[FLOOR]" in out


def test_redact_phone_masks_tail_only():
    assert redact_phone("+971501234567") == "[PHONE …67]"


def test_disabled_is_noop():
    text = "Apartment 1204, +971501234567"
    assert redact_text(text, enabled=False) == text
    assert redact_phone("+971501234567", enabled=False) == "+971501234567"


def test_redact_location_pair():
    assert redact_location(25.08, 55.14) == ("[COORDS]", "[COORDS]")
