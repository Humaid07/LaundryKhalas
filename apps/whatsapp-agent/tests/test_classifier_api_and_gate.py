"""Stage 2 — classifier API endpoints + routing gate.

Endpoint tests run in SQLite mode (conftest): the list endpoint degrades to an
empty list, and correction requires Supabase (503). The routing gate is a pure
function tested directly against the settings flags.
"""
from __future__ import annotations

from classifier.router import RouteDecision, should_route_via_classifier
from classifier.schema import Classification
from settings import get_settings


# ---------------------------------------------------------------------------
# API endpoints (offline / SQLite-mode behaviour)
# ---------------------------------------------------------------------------
async def test_list_classifications_empty_in_sqlite(client):
    resp = await client.get("/api/conversations/abc/classifications")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_correction_requires_supabase(client):
    resp = await client.post(
        "/api/conversations/abc/classifications/xyz/correction",
        json={"corrected_by": "ops", "primary_intent": "GREETING"},
    )
    # SQLite mode → inbox correction requires Supabase
    assert resp.status_code == 503


# ---------------------------------------------------------------------------
# Routing gate (pure, flag-gated)
# ---------------------------------------------------------------------------
def _decision(route="MAIN_AGENT"):
    return RouteDecision(route=route)


def test_gate_off_in_shadow_mode(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "whatsapp_classifier_shadow_mode", True)
    monkeypatch.setattr(s, "whatsapp_classifier_allow_routing", True)
    c = Classification(primary_intent="GREETING", intent_confidence=0.99)
    assert should_route_via_classifier(c, _decision(), s) is False


def test_gate_off_when_routing_disabled(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "whatsapp_classifier_shadow_mode", False)
    monkeypatch.setattr(s, "whatsapp_classifier_allow_routing", False)
    c = Classification(primary_intent="GREETING", intent_confidence=0.99)
    assert should_route_via_classifier(c, _decision(), s) is False


def test_gate_on_for_low_risk_high_confidence(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "whatsapp_classifier_shadow_mode", False)
    monkeypatch.setattr(s, "whatsapp_classifier_allow_routing", True)
    c = Classification(primary_intent="GREETING", intent_confidence=0.99,
                       conversation_route="DETERMINISTIC_HANDLER")
    assert should_route_via_classifier(c, _decision("DETERMINISTIC_HANDLER"), s) is True


def test_gate_rejects_high_risk_intent(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "whatsapp_classifier_shadow_mode", False)
    monkeypatch.setattr(s, "whatsapp_classifier_allow_routing", True)
    c = Classification(primary_intent="REFUND_REQUEST", intent_confidence=0.99)
    assert should_route_via_classifier(c, _decision(), s) is False


def test_gate_rejects_low_confidence(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "whatsapp_classifier_shadow_mode", False)
    monkeypatch.setattr(s, "whatsapp_classifier_allow_routing", True)
    c = Classification(primary_intent="SERVICE_SELECTION", intent_confidence=0.5)
    assert should_route_via_classifier(c, _decision(), s) is False


def test_gate_rejects_human_or_clarification(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "whatsapp_classifier_shadow_mode", False)
    monkeypatch.setattr(s, "whatsapp_classifier_allow_routing", True)
    c = Classification(primary_intent="SERVICE_SELECTION", intent_confidence=0.99,
                       needs_clarification=True)
    assert should_route_via_classifier(c, _decision(), s) is False
