"""Phase 1: the active behaviour rules are injected into the live Sonnet prompt."""
import rules
from agents.whatsapp_agent.booking_tools import booking_system_prompt


def test_prompt_contains_all_active_behaviour_rules():
    prompt = booking_system_prompt()
    for text in rules.behaviour_rule_texts():
        anchor = text.split(" - ")[0].split(".")[0].strip()  # stable leading clause
        assert anchor in prompt, f"behaviour rule missing from prompt: {anchor!r}"


def test_prompt_uses_correct_brand_and_not_typo():
    prompt = booking_system_prompt()
    assert "Laundry Khalas" in prompt
    assert "Khalaas" not in prompt


def test_prompt_no_longer_forces_single_message():
    prompt = booking_system_prompt().lower()
    assert "exactly one concise confirmation" not in prompt
    assert "keep each reply to one short message" not in prompt


def test_prompt_allows_one_to_three_messages():
    assert "1, 2, or at most 3" in booking_system_prompt()
