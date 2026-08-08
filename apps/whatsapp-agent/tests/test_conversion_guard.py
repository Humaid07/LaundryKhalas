"""Phase 2: detect and suppress unnecessary conversion CTAs (spec §4 / §16)."""
from services.conversion_guard import is_conversion_cta, recent_cta_count, strip_trailing_cta


def test_detects_booking_ctas():
    for t in [
        "Would you like to proceed?",
        "Shall I book this for you?",
        "Would you like me to arrange pickup?",
        "Do you want to go ahead?",
        "Would you still like to proceed?",
        "Would you like to book?",
    ]:
        assert is_conversion_cta(t), t


def test_operational_question_is_not_cta():
    for t in [
        "Please send me the pickup address.",
        "Please share the location pin as well.",
        "We have 2 PM-4 PM or 5 PM-7 PM available. Which one works better?",
        "The final price is AED 140. Shall I proceed with the work?",
        "Is it cleaning only or restoration as well?",
    ]:
        assert not is_conversion_cta(t), t


def test_plain_answer_is_not_cta():
    assert not is_conversion_cta("Clean and Press for 5 shirts is AED 45.")
    assert not is_conversion_cta("Yes, we collect from Dubai Marina.")


def test_recent_cta_count():
    msgs = ["24 hours. Would you like to book?", "Yes we collect from Marina.",
            "Shall I book this for you?"]
    assert recent_cta_count(msgs) == 2
    assert recent_cta_count([]) == 0


def test_strip_trailing_cta_removes_appended_sales_question():
    t = "Clean and Press for 5 shirts is AED 45. Would you like me to arrange the booking?"
    assert strip_trailing_cta(t) == "Clean and Press for 5 shirts is AED 45."


def test_strip_keeps_text_without_cta():
    t = "Yes, we collect from Dubai Marina."
    assert strip_trailing_cta(t) == t


def test_strip_keeps_operational_question():
    t = "The final price is AED 140. Shall I proceed with the work?"
    assert strip_trailing_cta(t) == t
