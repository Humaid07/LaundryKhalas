"""Website Order-Now intent capture + abandonment gating (spec §24)."""
import datetime as _dt

import pytest

from services import clock
from services import followups as fu
from services import followup_scheduler as fs
from services import web_order_intent as woi

_TZ = clock.zone_for_market("AE")


# --- pure decision (consent + verified number gating; no fingerprinting) -----
def test_no_number_no_outreach():
    d = woi.evaluate_intent(woi.WebOrderIntentInput(session_id="s1"))
    assert d.schedule_outreach is False and d.reason == "no_verified_number"
    assert d.normalized_number is None


def test_number_without_consent_no_outreach():
    d = woi.evaluate_intent(woi.WebOrderIntentInput(
        session_id="s1", whatsapp_number="+971501234567", consent=False))
    assert d.schedule_outreach is False and d.reason == "no_consent"
    assert d.normalized_number == "+971501234567"


def test_identified_consented_schedules_outreach():
    d = woi.evaluate_intent(woi.WebOrderIntentInput(
        session_id="s1", whatsapp_number="971501234567", consent=True))
    assert d.schedule_outreach is True and d.reason == "identified_consented"
    assert d.normalized_number == "+971501234567"


def test_invalid_number_is_not_outreach():
    d = woi.evaluate_intent(woi.WebOrderIntentInput(
        session_id="s1", whatsapp_number="not-a-number", consent=True))
    assert d.schedule_outreach is False and d.reason == "no_verified_number"


# --- abandonment builder: dedupe scoped to web session, no conversation ------
def test_web_abandonment_rows_scoped_to_session():
    click = _dt.datetime(2026, 8, 5, 10, 0, tzinfo=_TZ)
    rows = fs.web_abandonment_rows("sess-1", click, market="AE", persona="Maya",
                                   customer_phone="+971501234567")
    assert [r["followup_type"] for r in rows] == [
        fu.WEB_ABANDONMENT_1, fu.WEB_ABANDONMENT_2, fu.WEB_ABANDONMENT_3]
    assert all(r["conversation_id"] is None for r in rows)          # no conversation yet
    assert all(r["customer_phone"] == "+971501234567" for r in rows)
    # dedupe keyed on the session, not a conversation
    assert rows[0]["dedupe_key"] == fu.dedupe_key("sess-1", fu.WEB_ABANDONMENT_1)


# --- endpoint (records always; outreach flag reflects the decision) ----------
async def test_endpoint_anonymous_click_logs_no_outreach(client):
    resp = await client.post("/api/web/order-intent",
                             json={"session_id": "s-anon", "source_page": "/pricing"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["outreach_scheduled"] is False and data["reason"] == "no_verified_number"
    assert data["intent_id"]


async def test_endpoint_consented_visitor_marks_outreach(client):
    resp = await client.post("/api/web/order-intent", json={
        "session_id": "s-conv", "whatsapp_number": "+971502222222", "consent": True,
        "service_code": "WASH_FOLD", "market": "AE",
        "campaign": {"utm_source": "google"}})
    assert resp.status_code == 200
    data = resp.json()
    assert data["outreach_scheduled"] is True and data["reason"] == "identified_consented"


async def test_endpoint_number_without_consent_no_outreach(client):
    resp = await client.post("/api/web/order-intent",
                             json={"session_id": "s-nc", "whatsapp_number": "+971503333333"})
    assert resp.json()["outreach_scheduled"] is False
    assert resp.json()["reason"] == "no_consent"
