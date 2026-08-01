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


# --- emoji removal (spec 2026-08-01) ---------------------------------------
_SMILE = "\U0001F60A"   # 😊
_CHECK = "✅"       # ✅
_PIN = "\U0001F4CD"     # 📍
_PARTY = "\U0001F389"   # 🎉
_THUMB = "\U0001F44D"   # 👍
_WARN = "⚠"        # ⚠
_BASKET = "\U0001F9FA"  # 🧺
_ALL_EMOJI = (_SMILE, _CHECK, _PIN, _PARTY, _THUMB, _WARN, _BASKET)


def test_emoji_removed_from_greeting():
    out = normalize(f"Hi Zoya, how can I help you today? {_SMILE}")
    assert out.text == "Hi Zoya, how can I help you today?"
    assert out.emoji_count == 1
    assert "emoji" in out.rules_applied
    assert not any(e in out.text for e in _ALL_EMOJI)


def test_emoji_removal_preserves_order_id_and_payment_link():
    url = "https://pay.stripe.com/checkout/LK-AE-1024"
    out = normalize(f"{_CHECK} Your order LK-AE-1024 is ready. Pay here: {url}")
    assert "LK-AE-1024" in out.text
    assert url in out.text
    assert _CHECK not in out.text
    assert out.emoji_count == 1


def test_emoji_removal_preserves_price_phone_email():
    out = normalize(f"Total is AED 120 {_PIN}. Call +971 50 123 4567 or email me@x.com {_PARTY}")
    assert "AED 120" in out.text
    assert "+971 50 123 4567" in out.text
    assert "me@x.com" in out.text
    assert out.emoji_count == 2
    assert not any(e in out.text for e in _ALL_EMOJI)


def test_multiple_and_decorative_emoji_removed():
    out = normalize(f"Great choice! {_PARTY}{_BASKET}{_THUMB} {_WARN}")
    # emoji removed; the exclamation is also normalised to a full stop (§4).
    assert out.text == "Great choice."
    assert out.emoji_count == 4


def test_no_emoji_input_reports_zero():
    out = normalize("Your total is AED 90. Shall I confirm?")
    assert out.emoji_count == 0
    assert "emoji" not in out.rules_applied


def test_emoji_and_dash_together():
    out = normalize(f"Pickup 6 PM - 8 PM {_CHECK}, takes 1-2 days {_SMILE}.")
    assert "6 PM to 8 PM" in out.text
    assert "1 to 2 days" in out.text
    assert out.emoji_count == 2
    assert "emoji" in out.rules_applied
    assert _CHECK not in out.text and _SMILE not in out.text


def test_representative_replies_are_emoji_free():
    for reply in REPLIES:
        out = normalize(reply)
        assert out.emoji_count == 0


# --- exclamation-mark removal (spec 2026-08-01 §4) -------------------------
def test_exclamations_become_full_stops():
    out = normalize("Great! Your order is confirmed!")
    assert out.text == "Great. Your order is confirmed."
    assert out.exclaim_count == 2
    assert "exclamation" in out.rules_applied


def test_mixed_exclaim_question_becomes_question():
    assert normalize("Really?!").text == "Really?"
    assert normalize("Sure!! done").text == "Sure. done"
    assert normalize("Wow!!!").text == "Wow."


def test_exclamation_preserves_order_id_and_url():
    out = normalize("Order LK-AE-1024 is ready!")
    assert "LK-AE-1024" in out.text and out.text.endswith("ready.")
    url = "https://pay.laundrykhalaas.com/checkout?ref=LK-1!"  # ! is part of the url
    out2 = normalize(f"Pay here: {url}")
    assert url in out2.text


def test_no_exclamation_reports_zero():
    out = normalize("Your total is AED 90. Shall I confirm?")
    assert out.exclaim_count == 0
    assert "exclamation" not in out.rules_applied


def test_representative_replies_output_has_no_exclamations():
    # Some representative inputs contain "!" (e.g. "Hi! ..."); the validator must
    # strip them so no exclamation reaches the customer.
    for reply in REPLIES:
        assert "!" not in normalize(reply).text
