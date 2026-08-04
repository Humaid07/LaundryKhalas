"""Tests for the evaluator and divergence detector."""
from __future__ import annotations

from replay_harness.core.models import ModelUsage, ReplayTurn, ToolCallCapture
from replay_harness.eval import divergence as dv
from replay_harness.eval.evaluator import evaluate_turn


def _turn(reply="", **kw):
    t = ReplayTurn(source_chat_id="c", turn_index=kw.pop("i", 0),
                   customer_message=kw.pop("cust", ""), agent_reply=reply)
    for k, v in kw.items():
        setattr(t, k, v)
    t.response_word_count = len(reply.split())
    return t


def _codes(findings):
    return {f.code for f in findings}


def test_emoji_flagged():
    t = _turn("Sure thing 😀")
    assert "emoji_in_reply" in _codes(evaluate_turn(t, {}))


def test_exclamation_flagged():
    assert "exclamation_mark" in _codes(evaluate_turn(_turn("Great news!"), {}))


def test_virtual_assistant_flagged():
    t = _turn("I am a virtual assistant here to help")
    assert "mentions_virtual_assistant" in _codes(evaluate_turn(t, {}))


def test_empty_reply_flagged():
    t = _turn("")
    assert "empty_reply" in _codes(evaluate_turn(t, {}))


def test_empty_reply_not_flagged_for_audio():
    t = _turn("", media_type="audio")
    assert "empty_reply" not in _codes(evaluate_turn(t, {}))


def test_long_reply_flagged():
    t = _turn(" ".join(["word"] * 80))
    assert "long_reply" in _codes(evaluate_turn(t, {}))


def test_duplicate_reply_flagged():
    t = _turn("How can I help?")
    assert "duplicate_reply" in _codes(evaluate_turn(t, {"prev_reply": "How can I help?"}))


def test_vat_readded_critical():
    t = _turn("The total is 100 plus 5% VAT")
    findings = evaluate_turn(t, {})
    assert any(f.code == "vat_readded" and f.severity == "CRITICAL" for f in findings)


def test_ai_reply_during_takeover_critical():
    t = _turn("Here is your price", human_intervention_status="human_takeover")
    t.usage = ModelUsage(output_tokens=42)
    findings = evaluate_turn(t, {})
    assert any(f.code == "ai_reply_during_takeover" and f.severity == "CRITICAL" for f in findings)


def test_open_ended_pickup_flagged():
    t = _turn("Sure, what time suits you?")
    assert "open_ended_pickup_question" in _codes(evaluate_turn(t, {}))


def test_open_ended_pickup_ok_when_slots_checked():
    t = _turn("Sure, what time suits you?")
    t.tool_calls = [ToolCallCapture(tool_name="get_pickup_slots")]
    assert "open_ended_pickup_question" not in _codes(evaluate_turn(t, {}))


# --- divergence ------------------------------------------------------------
def test_divergence_when_customer_does_not_answer():
    prev = _turn("Can you share your location pin?")
    cur = _turn(cust="2 shirts and one trouser")
    d = dv.detect(prev, cur)
    assert d is not None
    assert d.divergence_type == dv.CUSTOMER_MESSAGE_DOES_NOT_ANSWER
    assert d.agent_requested_field == "location_pin"


def test_no_divergence_when_customer_answers():
    prev = _turn("Which area is the pickup?")
    cur = _turn(cust="Dubai Marina, Marina Heights tower")
    assert dv.detect(prev, cur) is None


def test_no_divergence_without_question():
    prev = _turn("Thanks, noted.")
    cur = _turn(cust="anything")
    assert dv.detect(prev, cur) is None
