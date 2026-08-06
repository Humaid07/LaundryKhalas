"""Revised-quote policy — deterministic customer price + state machine (Area 6)."""
from services import quote_revision as qr


def test_percentage_margin():
    assert qr.compute_customer_price(100, {"margin_type": "percentage", "margin_value": 30}) == 130.0


def test_fixed_margin():
    assert qr.compute_customer_price(100, {"margin_type": "fixed", "margin_value": 20}) == 120.0


def test_default_rule_is_used_when_none():
    # Grounded in a rule (default 30%), never invented ad hoc.
    assert qr.compute_customer_price(50, None) == 65.0


def test_validate_fee():
    assert qr.validate_fee(10) is True
    assert qr.validate_fee(0) is False
    assert qr.validate_fee(-5) is False
    assert qr.validate_fee("abc") is False


def test_state_machine_transitions():
    assert qr.can_transition("pending_ops_review", "customer_pending") is True
    assert qr.can_transition("pending_ops_review", "ops_rejected") is True
    assert qr.can_transition("customer_pending", "customer_approved") is True
    assert qr.can_transition("customer_pending", "customer_rejected") is True
    # illegal jumps
    assert qr.can_transition("pending_ops_review", "customer_approved") is False
    assert qr.can_transition("customer_approved", "customer_pending") is False
    assert qr.can_transition("ops_rejected", "customer_approved") is False


def test_unblocks_only_on_customer_approval():
    assert qr.UNBLOCKS_WORK == "customer_approved"
    assert "customer_approved" in qr.TERMINAL
    assert "ops_rejected" in qr.TERMINAL
