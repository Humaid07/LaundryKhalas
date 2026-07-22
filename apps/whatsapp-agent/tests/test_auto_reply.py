"""Tests for the auto-reply decision layer (services/auto_reply.py)."""
from services.auto_reply import (
    ESCALATION,
    GREETING_ONLY,
    LAUNDRY_RELATED,
    OUT_OF_DOMAIN,
    should_auto_reply,
)


# --- laundry-related -> auto-reply -----------------------------------------
def test_laundry_pickup_greeting_replies_and_continues():
    d = should_auto_reply("Hi, I need laundry pickup today", {"welcome_sent": False})
    assert d.send_reply is True
    assert d.domain == LAUNDRY_RELATED


def test_pricing_question_replies_even_if_already_welcomed():
    d = should_auto_reply("what are your rates for wash and fold?", {"welcome_sent": True})
    assert d.send_reply is True
    assert d.domain == LAUNDRY_RELATED
    assert d.allow_welcome is False  # already welcomed


# --- escalation -> never auto-resolve --------------------------------------
def test_refund_is_escalation_no_auto_reply():
    d = should_auto_reply("I want a refund. My clothes came back dirty.", {})
    assert d.send_reply is False
    assert d.domain == ESCALATION
    assert d.intent == "escalation_refund"


def test_damaged_item_is_escalation():
    d = should_auto_reply("my shirt was damaged and a sock is missing", {})
    assert d.send_reply is False
    assert d.domain == ESCALATION


# --- bare greeting -> welcome once, then silent ----------------------------
def test_first_bare_greeting_sends_welcome_once():
    d = should_auto_reply("hi", {"welcome_sent": False})
    assert d.send_reply is True
    assert d.domain == GREETING_ONLY
    assert d.allow_welcome is True


def test_repeat_greeting_stays_silent():
    d = should_auto_reply("hello", {"welcome_sent": True})
    assert d.send_reply is False
    assert d.domain == GREETING_ONLY


def test_good_morning_phrase_is_greeting():
    d = should_auto_reply("good morning", {"welcome_sent": False})
    assert d.send_reply is True
    assert d.domain == GREETING_ONLY


# --- unrelated / smalltalk -> silent ---------------------------------------
def test_hello_bro_is_not_a_bare_greeting():
    d = should_auto_reply("hello bro", {"welcome_sent": False})
    assert d.send_reply is False
    assert d.domain == OUT_OF_DOMAIN


def test_examples_that_must_not_auto_reply():
    for text in [
        "what are you doing",
        "test",
        "okay",
        "thanks",
        "hmm",
        "👋😊",  # emoji only
        "who is the president",
        "write me some python code",
    ]:
        d = should_auto_reply(text, {"welcome_sent": False})
        assert d.send_reply is False, f"should not auto-reply to: {text!r}"


def test_emoji_only_is_empty_domain():
    d = should_auto_reply("🔥🔥🔥", {})
    assert d.send_reply is False
    assert d.intent == "empty"
