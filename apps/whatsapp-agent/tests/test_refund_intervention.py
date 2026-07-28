"""Refund → human-intervention: detection coverage + the approved acknowledgement
is safe (never approves/promises/quotes a refund). The durable-pause + idempotency
webhook flow is proven by the live integration verification (see the build report);
these are the fast deterministic guards."""
import pytest

from services.escalation import detect_escalation


@pytest.mark.parametrize("text", [
    "I want a refund.",
    "Please refund my money.",
    "I need my money back.",
    "Can you reverse the payment?",
    "I paid twice.",
    "I want to cancel and get a refund.",
    "This order was not completed, refund me.",
    "I want compensation and a refund.",
    "Please return the amount.",
    "That payment should be reversed.",
    "Give me my money back.",
    "You charged me wrong.",
    "I was charged incorrectly.",
])
def test_refund_language_is_detected(text):
    assert detect_escalation(text) == "refund"


@pytest.mark.parametrize("text", [
    "I want to book a wash and fold",
    "How much is shirt cleaning?",
    "tomorrow after 6",
    "from Dubai Marina",
])
def test_non_refund_language_not_flagged_as_refund(text):
    assert detect_escalation(text) != "refund"


def test_refund_acknowledgement_is_safe():
    # The single approved refund notice must never approve / promise / quote.
    from api.evolution_webhooks import _REFUND_ACK_TEXT

    low = _REFUND_ACK_TEXT.lower()
    assert "operations" in low and "review" in low
    for forbidden in ("approved", "processed", "eligible", "you will receive",
                      "3 days", "three days", "aed ", "against policy", "cannot refund"):
        assert forbidden not in low
