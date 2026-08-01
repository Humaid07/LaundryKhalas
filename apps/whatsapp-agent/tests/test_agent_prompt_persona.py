"""Stage 2 — system-prompt assembly: persona (§1), order flow (§2.12), and the
AED/QAR currency overlay (§8) pulled from config.

The prompt builders are pure string assemblers, so these assert the config values
flow through and no ungrounded/unsafe wording leaks (e.g. the placeholder name).
"""
from __future__ import annotations

import pytest

from agents.whatsapp_agent.booking_tools import booking_system_prompt


# --------------------------------------------------------------------------
# Persona (§1) — the STABLE prompt uses the backend-assigned name (not a baked one)
# --------------------------------------------------------------------------
def test_stable_prompt_references_backend_assigned_name_not_a_baked_one():
    bp = booking_system_prompt()
    # The stable prompt carries the placeholder + the hard rule, never a real name.
    assert "{{assigned_ai_persona_name}}" in bp
    assert "assistant_identity.display_name" in bp
    assert "never select, change or invent" in bp.lower()
    # No specific approved persona name is baked into the STABLE prompt.
    for name in ("Sara", "Maya", "Zoya", "Hanna", "Sofia", "Max", "Ben"):
        assert name not in bp


def test_persona_separate_from_human_staff_in_prompt():
    bp = booking_system_prompt()
    assert "SEPARATE from the human Operations team" in bp
    assert "human" in bp.lower()


def test_presents_as_customer_service_rep_not_virtual_assistant():
    bp = booking_system_prompt()
    low = bp.lower()
    # New contract: present as a customer service representative, never a virtual assistant.
    # The agent must not IDENTIFY as a virtual assistant (the old positive self-description
    # is gone); the phrase now survives only inside the negative disclosure rule
    # ("do not describe yourself as a virtual assistant ...").
    assert "whatsapp virtual assistant" not in low
    assert "a laundry khalaas customer service representative" in low
    assert "do not describe yourself as a virtual assistant" in low
    assert "customer service representative" in low
    # Human-disclosure rule: don't claim to be human, don't fabricate an identity.
    assert "do not claim to be human" in low
    # Process step wording (never claim the absolute nearest facility).
    assert "one of the nearest suitable facilities" in low


def test_no_emojis_and_no_service_list_on_greeting():
    bp = booking_system_prompt()
    low = bp.lower()
    # No emojis in customer-facing replies.
    assert "no emojis" in low
    assert "never use emojis" in low
    # Do not list services on a normal greeting.
    assert "do not list the services" in low


def test_arabic_language_instruction_present():
    bp = booking_system_prompt()
    assert "Arabic" in bp


# --------------------------------------------------------------------------
# Currency overlay (§8)
# --------------------------------------------------------------------------
def test_currency_overlay_present():
    bp = booking_system_prompt()
    assert "currency" in bp.lower()
    assert "QAR" in bp and "AED" in bp
    assert "pricing_configured" in bp            # routes unpriced markets to a human


# --------------------------------------------------------------------------
# Order flow (§2.12)
# --------------------------------------------------------------------------
@pytest.mark.parametrize("needle", [
    "photo",                # specialty photo-gate
    "alterations start from AED",   # standard alterations = starting price, no photo (§5)
    "room number",          # hotels
    "15–30 minutes",   # driver contact window
    "reception",            # leave-with fallbacks
    "cash off-system",      # payment guardrail
    "walk-in",              # steer to pickup
])
def test_flow_elements_present(needle):
    assert needle in booking_system_prompt()


def test_payment_prefers_card_but_allows_cash():
    bp = booking_system_prompt()
    assert "card payment" in bp
    assert "cash" in bp
    assert "do NOT create or promise a payment link" in bp


# --------------------------------------------------------------------------
# Market/currency block feeding the model (services/market via clock block)
# --------------------------------------------------------------------------
def test_market_block_currency_by_market():
    from services import market
    market.reload_markets()
    assert market.get_market("AE").currency == "AED"
    assert market.get_market("UAE").currency == "AED"       # alias
    assert market.get_market("Qatar").currency == "QAR"     # alias
    assert market.get_market("QA").pricing_configured is True   # QA priced via the QAR overlay
