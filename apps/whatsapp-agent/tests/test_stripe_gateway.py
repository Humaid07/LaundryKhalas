"""Phase A — Stripe config gating + mock gateway (no live calls anywhere).

These tests pin the mock-first contract for the payments layer, mirroring the
LLM layer: a real Stripe provider is selected ONLY when STRIPE_MODE is test/live
AND a key is present; otherwise every call goes through the deterministic mock
that performs no I/O. Nothing here touches the network.
"""
from __future__ import annotations

import json

import pytest

from services.payments import base
from services.payments.gateway import get_gateway
from services.payments.mock_provider import MockStripeGateway
from settings import Settings


def _settings(**overrides) -> Settings:
    # _env_file=None keeps these hermetic — never read a developer's local .env.
    return Settings(_env_file=None, **overrides)


# --- config gating ----------------------------------------------------------
def test_stripe_mode_defaults_to_mock():
    assert _settings().stripe_mode_normalized == "mock"


def test_unknown_stripe_mode_resolves_to_mock_failsafe():
    assert _settings(stripe_mode="banana").stripe_mode_normalized == "mock"


def test_mock_mode_is_never_live_ready_even_with_a_key():
    s = _settings(stripe_mode="mock", stripe_secret_key="rk_test_abc")
    assert s.stripe_live_ready is False


def test_test_mode_needs_a_key_to_be_live_ready():
    assert _settings(stripe_mode="test").stripe_live_ready is False
    assert _settings(stripe_mode="test", stripe_secret_key="rk_test_abc").stripe_live_ready is True


def test_validate_stripe_config_raises_when_test_mode_missing_key():
    with pytest.raises(ValueError, match="STRIPE_SECRET_KEY"):
        _settings(stripe_mode="test").validate_stripe_config()


def test_validate_stripe_config_rejects_live_key_in_test_mode():
    # A live key while STRIPE_MODE=test is a dangerous mismatch — fail fast.
    with pytest.raises(ValueError, match="test mode"):
        _settings(stripe_mode="test", stripe_secret_key="rk_live_abc").validate_stripe_config()


def test_validate_stripe_config_rejects_test_key_in_live_mode():
    with pytest.raises(ValueError, match="live-mode"):
        _settings(stripe_mode="live", stripe_secret_key="rk_test_abc").validate_stripe_config()


def test_validate_stripe_config_mock_never_raises():
    # mock mode requires nothing.
    _settings(stripe_mode="mock").validate_stripe_config()


def test_stripe_status_never_leaks_the_key():
    s = _settings(stripe_mode="test", stripe_secret_key="rk_test_supersecret")
    status = s.stripe_status
    assert "rk_test_supersecret" not in json.dumps(status)
    assert status["mode"] == "test"
    assert status["configured"] is True
    assert status["live"] is False  # test mode is not "live"


# --- provider selection -----------------------------------------------------
def test_get_gateway_returns_mock_in_mock_mode(monkeypatch):
    monkeypatch.setattr("services.payments.gateway.get_settings",
                        lambda: _settings(stripe_mode="mock"))
    assert isinstance(get_gateway(), MockStripeGateway)


def test_get_gateway_returns_mock_when_test_mode_but_no_key(monkeypatch):
    monkeypatch.setattr("services.payments.gateway.get_settings",
                        lambda: _settings(stripe_mode="test", stripe_secret_key=""))
    assert isinstance(get_gateway(), MockStripeGateway)


# --- mock gateway behaviour -------------------------------------------------
def _invoice_request(**kw) -> base.InvoiceRequest:
    return base.InvoiceRequest(
        customer=base.PaymentCustomer(name="Aisha", email="a@example.com", country="AE"),
        line_items=[
            base.InvoiceLineItem(description="Wash & Fold 6kg", amount_minor=5400),
            base.InvoiceLineItem(description="Express surcharge", amount_minor=1500, quantity=2),
        ],
        currency="aed",
        order_id="LK-AE-2001",
        **kw,
    )


async def test_mock_invoice_sums_line_items_and_is_flagged_mock():
    result = await MockStripeGateway().create_invoice(_invoice_request())
    assert result.is_mock is True
    assert result.provider == "mock"
    # 5400 + 1500*2 = 8400 minor units
    assert result.amount_due_minor == 8400
    assert result.currency == "aed"


async def test_mock_invoice_returns_hosted_url_and_ids():
    result = await MockStripeGateway().create_invoice(_invoice_request())
    assert result.invoice_id.startswith("in_mock_")
    assert result.customer_id.startswith("cus_mock_")
    assert result.hosted_invoice_url and result.hosted_invoice_url.startswith("https://")
    assert result.invoice_pdf_url


async def test_mock_invoice_is_deterministic_for_the_same_order():
    r1 = await MockStripeGateway().create_invoice(_invoice_request(idempotency_key="k1"))
    r2 = await MockStripeGateway().create_invoice(_invoice_request(idempotency_key="k1"))
    assert r1.invoice_id == r2.invoice_id


def test_mock_parse_webhook_event_reads_json():
    payload = json.dumps({
        "id": "evt_mock_1",
        "type": "invoice.paid",
        "data": {"object": {"id": "in_mock_x", "metadata": {"order_id": "LK-AE-2001"}}},
    }).encode()
    event = MockStripeGateway().parse_webhook_event(payload, signature=None)
    assert event.id == "evt_mock_1"
    assert event.type == "invoice.paid"
    assert event.data["metadata"]["order_id"] == "LK-AE-2001"
    assert event.is_mock is True


def test_mock_parse_webhook_event_rejects_garbage():
    with pytest.raises(ValueError):
        MockStripeGateway().parse_webhook_event(b"not json", signature=None)
