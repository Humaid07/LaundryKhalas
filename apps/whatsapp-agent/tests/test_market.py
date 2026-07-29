"""Tests for market / currency resolution (spec §8)."""
from __future__ import annotations

import pytest

from services import market


@pytest.fixture(autouse=True)
def _fresh():
    market.reload_markets()
    yield
    market.reload_markets()


@pytest.mark.parametrize("phone,currency", [
    ("+971501234567", "AED"),
    ("971501234567", "AED"),
    ("+97455512345", "QAR"),
    ("97455512345", "QAR"),
])
def test_market_for_phone(phone, currency):
    assert market.currency_for_phone(phone) == currency


def test_unknown_prefix_falls_back_to_default():
    m = market.market_for_phone("+15551234567")
    assert m.code == market.default_market_code()
    assert m.currency == "AED"


def test_none_phone_uses_default():
    assert market.currency_for_phone(None) == "AED"


def test_pricing_configured_flags():
    assert market.pricing_configured_for_phone("+971501234567") is True
    assert market.pricing_configured_for_phone("+97455512345") is True    # QAR now priced (QA overlay)


@pytest.mark.parametrize("amount,code,expected", [
    (60, "AE", "AED 60"),
    (52.5, "AE", "AED 52.50"),
    (60, "QA", "QAR 60"),
])
def test_format_price(amount, code, expected):
    assert market.format_price(amount, code) == expected


def test_never_mixes_currencies():
    """A QA customer must never be quoted in AED."""
    qa = market.market_for_phone("+97455512345")
    assert market.format_price(60, qa.code).startswith("QAR")
