"""Behaviour matrix §17 — scenario 1: the deterministic "how does it work" guide.

Pure, offline, no LLM. Asserts the REQUIRED behaviour of services/process_guide:
intent detection for "how does it work / what is your process / how do I order /
what happens after I book" and the exact four-step explanation contract (Stripe
payment link + delivery, "one of the nearest suitable facilities", no dash
bullets, no emoji). The explanation is additionally run through the customer
reply-style normaliser to prove it is already dash-free and emoji-free.

The style normaliser itself (dash/emoji removal) is covered by test_reply_style;
here we only assert the guide TEXT already satisfies that contract unchanged.
"""
from __future__ import annotations

import pytest

from services import process_guide as pg
from services.reply_style import normalize_customer_reply


# --------------------------------------------------------------------------- #
# Intent detection (§5) — process questions vs a booking request
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("text", [
    "How does it work?",
    "What is your process?",
    "how do I place an order?",
    "what happens after I book?",
    "how do you all work?",
])
def test_process_questions_detected(text):
    assert pg.is_process_question(text) is True


@pytest.mark.parametrize("text", [
    "book a wash and fold",
    "I need 3 shirts dry cleaned",
    "hi",
    "",
    None,
])
def test_non_process_messages_not_detected(text):
    assert pg.is_process_question(text) is False


# --------------------------------------------------------------------------- #
# The explanation contract (§5)
# --------------------------------------------------------------------------- #

def test_explanation_has_exactly_four_numbered_steps():
    text = pg.process_explanation()
    # Steps are the ONLY place numbered lists are allowed. Exactly 1..4 present.
    for n in (1, 2, 3, 4):
        assert f"{n}." in text
    assert "5." not in text


def test_explanation_uses_one_of_the_nearest_suitable_facilities():
    # Never claims the absolute nearest facility — backend validates selection.
    assert "one of the nearest suitable facilities" in pg.process_explanation()


def test_explanation_mentions_stripe_payment_link_and_delivery():
    low = pg.process_explanation().lower()
    assert "stripe" in low
    assert "payment link" in low
    assert "deliver" in low  # "dispatch it for delivery"


def test_explanation_has_no_dash_bullets_and_no_emoji():
    text = pg.process_explanation()
    # No literal em/en dashes anywhere in the guide prose.
    assert "–" not in text and "—" not in text
    # No dash bullet line starts.
    assert not any(line.lstrip().startswith(("- ", "– ", "— ", "* "))
                   for line in text.splitlines())
    # Run through the customer reply-style safety net: already clean → unchanged,
    # valid, and zero emoji removed.
    result = normalize_customer_reply(text)
    assert result.emoji_count == 0
    assert result.valid is True
    assert result.text == text  # nothing to rewrite — the guide is already compliant
