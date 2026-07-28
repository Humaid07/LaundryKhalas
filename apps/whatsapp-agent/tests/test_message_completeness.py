"""Deterministic message-completeness classifier + adaptive debounce mapping
(response-timing spec). Pure/local — no DB, no LLM, no network."""
import pytest

from services import message_completeness as mc
from services.message_completeness import Completeness as C


# --- COMPLETE natural-language messages (short/standard wait, not max) --------
@pytest.mark.parametrize("text", [
    "How much is shirt cleaning?",
    "Can you pick up today after 6 PM?",
    "My name is Sara and I need four shirts cleaned and pressed tomorrow.",
    "Change the pickup time to 8 PM.",
    "What is the price for dry cleaning a suit?",
    "My name is Sara. I need four shirts cleaned and pressed tomorrow after 6 PM from Marina.",
])
def test_complete_messages(text):
    assert mc.classify(text) == C.COMPLETE


# --- LIKELY_FRAGMENT (short/continuation, wait longer to combine) ------------
@pytest.mark.parametrize("text", [
    "Hi", "Hello", "I need laundry", "tomorrow", "after six", "from Marina",
    "and", "also please",
])
def test_fragments(text):
    assert mc.classify(text) == C.LIKELY_FRAGMENT


# --- STRUCTURED_ACTION (list/button/slot selection, location pin) ------------
@pytest.mark.parametrize("selection_id", ["service:HOME_CARE", "slot:s1", "item:X", "sub:Y"])
def test_structured_selection(selection_id):
    assert mc.classify("", selection_id=selection_id) == C.STRUCTURED_ACTION


def test_location_pin_is_structured():
    assert mc.classify("", has_location=True) == C.STRUCTURED_ACTION


# --- URGENT_OPERATIONAL_ACTION (explicit confirm / cancel) -------------------
@pytest.mark.parametrize("text", [
    "Yes, confirm the order.", "Confirm", "Please confirm", "Cancel my order.",
    "cancel order", "Yes confirm",
])
def test_urgent_confirm_cancel(text):
    assert mc.classify(text) == C.URGENT_OPERATIONAL_ACTION


def test_confirm_selection_is_urgent():
    assert mc.classify("", selection_id="confirm_booking") == C.URGENT_OPERATIONAL_ACTION
    assert mc.classify("", selection_id="cancel_booking") == C.URGENT_OPERATIONAL_ACTION


def test_answers_requested_field_is_complete():
    # "tomorrow" alone is a fragment, but IS complete when it answers the field
    # the agent just asked for.
    assert mc.classify("tomorrow") == C.LIKELY_FRAGMENT
    assert mc.classify("tomorrow", answers_requested_field=True) == C.COMPLETE


def test_reasonable_sentence_is_likely_complete():
    assert mc.classify("I would like to book a pickup for my clothes please") == C.LIKELY_COMPLETE


# --- Debounce tier mapping ---------------------------------------------------
def test_debounce_tier_mapping():
    short, standard, fragment = 0.5, 1.0, 3.0

    def d(label):
        return mc.debounce_seconds(label, short_s=short, standard_s=standard, fragment_s=fragment)

    assert d(C.STRUCTURED_ACTION) == short
    assert d(C.URGENT_OPERATIONAL_ACTION) == short
    assert d(C.COMPLETE) == standard
    assert d(C.LIKELY_COMPLETE) == standard
    assert d(C.LIKELY_FRAGMENT) == fragment
    # A complete message must NOT wait the long fragment window.
    assert d(C.COMPLETE) < d(C.LIKELY_FRAGMENT)
    # A structured action uses the shortest wait.
    assert d(C.STRUCTURED_ACTION) <= d(C.COMPLETE)
