"""Sender allow-list gate for Evolution auto-reply (the safety fix).

Covers the required behaviour: during testing the agent must ONLY auto-reply to
approved test numbers, and even then only to safe, laundry-related messages
(welcome once). Everything here is pure — no DB, no network.
"""
from services.auto_reply import (
    SENDER_NOT_ALLOWED,
    evaluate_inbound,
    should_auto_reply,
)
from services.privacy import normalize_e164
from settings import Settings

ALLOWED = frozenset({"+971502485658"})           # the one approved test number
STRANGER_JID = "971509998888@s.whatsapp.net"     # some other WhatsApp number


# --- number normalization (Evolution / Baileys JID shapes) -----------------
def test_normalize_handles_every_inbound_shape():
    for raw in [
        "971502485658@s.whatsapp.net",
        "whatsapp:+971502485658",
        "+971 50 248 5658",
        "971502485658",
        "+971502485658",
    ]:
        assert normalize_e164(raw) == "+971502485658", raw


def test_normalize_empty_is_blank():
    assert normalize_e164("") == ""
    assert normalize_e164(None) == ""


# --- settings parse a comma-separated allow-list ---------------------------
def test_settings_parses_comma_separated_allow_list():
    s = Settings(
        _env_file=None,
        evolution_allowed_test_numbers="+971502485658, 971509998888@s.whatsapp.net",
    )
    assert s.allowed_auto_reply_numbers == frozenset(
        {"+971502485658", "+971509998888"}
    )


def test_settings_empty_allow_list_is_fail_safe():
    s = Settings(_env_file=None, evolution_allowed_test_numbers="")
    assert s.allowed_auto_reply_numbers == frozenset()


# === the five required scenarios ===========================================

# 1) Allowed number + laundry message => auto-reply allowed
def test_allowed_number_laundry_message_replies():
    d = evaluate_inbound(
        STRANGER_JID.replace("971509998888", "971502485658"),
        "Hi, I need laundry pickup today",
        ALLOWED,
    )
    assert d.allowed_sender is True
    assert d.send_reply is True
    assert d.auto_reply_decision == "send"


# 2) Allowed number + unrelated message => no auto-reply
def test_allowed_number_unrelated_message_stays_silent():
    d = evaluate_inbound("+971502485658", "hello bro", ALLOWED)
    assert d.allowed_sender is True
    assert d.send_reply is False
    assert d.no_auto_reply_reason  # a reason is recorded, but nothing is sent


# 3) Unapproved number + laundry message => no reply, reason sender_not_allowed
def test_stranger_laundry_message_blocked_by_sender_gate():
    d = evaluate_inbound(STRANGER_JID, "Hi, I need laundry pickup", ALLOWED)
    assert d.allowed_sender is False
    assert d.send_reply is False
    assert d.no_auto_reply_reason == SENDER_NOT_ALLOWED
    # the message decision is never even run for a stranger
    assert d.message is None


# 4) Unapproved number + refund => no reply; NO customer-facing draft at all
def test_stranger_refund_message_creates_no_customer_reply():
    d = evaluate_inbound("whatsapp:+971509998888", "I want a refund", ALLOWED)
    assert d.allowed_sender is False
    assert d.send_reply is False
    assert d.no_auto_reply_reason == SENDER_NOT_ALLOWED
    assert d.message is None  # gate short-circuits before any reply is composed


# 5) Allowed number repeated "hi" => welcome must not repeat every time
def test_welcome_sent_once_not_on_every_greeting():
    first = evaluate_inbound("+971502485658", "hi", ALLOWED, {"welcome_sent": False})
    assert first.send_reply is True  # first greeting -> welcome once

    second = evaluate_inbound("+971502485658", "hi", ALLOWED, {"welcome_sent": True})
    assert second.send_reply is False  # already welcomed -> silent


# --- escalation from an ALLOWED sender is still never auto-answered ---------
def test_allowed_number_refund_is_held_for_human():
    d = evaluate_inbound(
        "+971502485658", "I want a refund. My clothes came back dirty.", ALLOWED
    )
    assert d.allowed_sender is True
    assert d.send_reply is False
    assert d.message is not None
    assert d.message.intent == "escalation_refund"


# --- the underlying message decision is unchanged for allowed senders ------
def test_should_auto_reply_still_used_for_allowed_sender():
    d = evaluate_inbound("+971502485658", "what are your rates?", ALLOWED)
    assert d.send_reply is should_auto_reply("what are your rates?").send_reply
