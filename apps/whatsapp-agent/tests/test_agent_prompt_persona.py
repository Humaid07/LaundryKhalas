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


def test_never_reveal_ai():
    assert "never reveal or imply" in booking_system_prompt().lower()
    assert "i am an ai" in booking_system_prompt().lower()


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
    "cm or inches",         # alterations measurement units
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
