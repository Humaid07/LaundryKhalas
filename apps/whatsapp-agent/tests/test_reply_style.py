"""Customer-reply style normaliser (no-dash) — deterministic, offline.

Covers the spec's required cases: representative replies contain no dash bullet
formatting, no en/em dashes, no dash time/turnaround ranges; immutable identifiers,
URLs, emails and refs are preserved byte-for-byte.
"""
import re

from services.reply_style import normalize_customer_reply as normalize

_DASHES = ("–", "—")  # en dash, em dash


def _no_dash_formatting(text: str) -> bool:
    """True when the text has no en/em dash, no dash bullet line, no hyphen-based
    numeric/time range, and no spaced-hyphen separator — outside identifiers."""
    if any(d in text for d in _DASHES):
        return False
    if re.search(r"(?m)^[ \t]*[-–—•]\s+", text):
        return False
    if re.search(r"\d\s*[-–—]\s*\d", text):
        return False
    if re.search(r"\s-\s", text):
        return False
    return True


# --- representative customer replies (spec list) ---------------------------
REPLIES = [
    "Hi! I'm Sara from Laundry Khalaas. How can I help with your laundry today?",
    "Sure, we can do a wash and fold for you. What items would you like cleaned?",
    "Please share your full pickup address and your WhatsApp location pin.",
    "Could you drop your WhatsApp location pin so we can route the driver?",
    "What pickup time would you prefer today?",
    "Your total is AED 90. Shall I confirm the pickup?",
    "Your original total is AED 600. After the approved discount, the final amount is AED 480.",
    "Here is your order summary. Wash and fold, pickup tomorrow evening, total AED 90.",
    "No problem, our team will treat the stain carefully and check it before delivery.",
    "Thanks for waiting. The facility is preparing your quotation and we will confirm shortly.",
    "I have passed this to a member of our team who will get back to you shortly.",
    "Thanks for your interest in a business account. Our team will reach out to discuss volumes.",
]


def test_representative_replies_have_no_dash_formatting():
    for reply in REPLIES:
        result = normalize(reply)
        assert _no_dash_formatting(result.text), f"dash formatting remained in: {result.text!r}"
        assert result.valid


def test_dash_bullet_list_becomes_plain_lines():
    src = "Please send:\n- Your address\n- Your location pin\n- Your pickup time"
    out = normalize(src)
    assert "- " not in out.text
    assert "Your address" in out.text and "Your location pin" in out.text
    assert "dash_bullet" in out.rules_applied
    assert out.valid


def test_time_range_uses_to():
    out = normalize("Pickup is available from 6 PM - 8 PM.")
    assert out.text == "Pickup is available from 6 PM to 8 PM."
    assert "time_range" in out.rules_applied


def test_turnaround_range_ascii_and_endash():
    assert normalize("The service takes 1-2 days.").text == "The service takes 1 to 2 days."
    assert normalize("The service takes 1–2 days.").text == "The service takes 1 to 2 days."


def test_em_dash_becomes_sentence_break():
    out = normalize("Your total is AED 600 — after the discount it is AED 480.")
    assert "—" not in out.text
    assert "AED 600" in out.text and "AED 480" in out.text


def test_order_id_is_preserved():
    for src in ("Your reference is LK-AE-1024.", "LK-AE-1024 is confirmed for 1-2 days."):
        out = normalize(src)
        assert "LK-AE-1024" in out.text


def test_payment_url_is_preserved():
    url = "https://pay.laundrykhalaas.com/checkout?ref=LK-AE-1024&amt=90-00"
    out = normalize(f"You can pay here: {url}")
    assert url in out.text


def test_email_and_phone_preserved():
    out = normalize("Email care-team@laundry-khalaas.com or call 050-123-4567.")
    assert "care-team@laundry-khalaas.com" in out.text
    assert "050-123-4567" in out.text


def test_coupon_code_preserved():
    out = normalize("Use code SAVE-20 at checkout for 1-2 day service.")
    assert "SAVE-20" in out.text
    assert "1 to 2 day" in out.text


def test_dash_count_and_change_flags():
    clean = normalize("Your total is AED 90. Shall I confirm?")
    assert not clean.changed and clean.dash_count == 0
    dirty = normalize("Pickup 6 PM - 8 PM, takes 1-2 days.")
    assert dirty.changed and dirty.dash_count >= 2


def test_empty_input_is_safe():
    for src in (None, "", "   "):
        out = normalize(src)
        assert out.text == (src or "")
        assert not out.changed
