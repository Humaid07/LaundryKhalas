"""Verifies the WhatsApp Operations Agent escalates instead of running its
happy-path order flow when the Classifier Agent has flagged the
conversation - see docs/architecture/classifier-agent.md.
"""
import pytest


@pytest.mark.asyncio
async def test_complaint_escalates_without_creating_order(client, admin_headers):
    inbound = await client.post(
        "/api/mock-whatsapp/inbound",
        json={
            "market_code": "AE",
            "phone_number": "+971500000070",
            "message": "This is unacceptable, my clothes are ruined!",
        },
    )
    conversation_id = inbound.json()["conversation_id"]

    run_result = await client.post(
        f"/api/admin/conversations/{conversation_id}/run-agent", headers=admin_headers
    )
    assert run_result.status_code == 200
    body = run_result.json()
    assert body["decision"] == "escalate"
    assert body["order_id"] is None
    assert body["approval_id"] is not None

    approval = await client.get(
        f"/api/admin/approvals/{body['approval_id']}", headers=admin_headers
    )
    assert approval.status_code == 200
    approval_body = approval.json()
    assert approval_body["action_type"] == "escalate_to_human"
    assert approval_body["reason"] == "classifier_flagged_intent=facility_issue"


@pytest.mark.asyncio
async def test_reschedule_request_escalates_instead_of_duplicate_order(client, admin_headers):
    # All three order slots (service_type, area, pickup_when) are present in
    # this message - without the classifier guard, decide_next_action would
    # extract them and create a brand new duplicate order instead of
    # recognizing this as a request to change an *existing* one.
    inbound = await client.post(
        "/api/mock-whatsapp/inbound",
        json={
            "market_code": "AE",
            "phone_number": "+971500000071",
            "message": "Please reschedule my wash and fold pickup to tomorrow afternoon, Marina",
        },
    )
    conversation_id = inbound.json()["conversation_id"]

    run_result = await client.post(
        f"/api/admin/conversations/{conversation_id}/run-agent", headers=admin_headers
    )
    assert run_result.status_code == 200
    body = run_result.json()
    assert body["decision"] == "escalate"
    assert body["order_id"] is None


@pytest.mark.asyncio
async def test_b2b_lead_escalates(client, admin_headers):
    inbound = await client.post(
        "/api/mock-whatsapp/inbound",
        json={
            "market_code": "AE",
            "phone_number": "+971500000072",
            "message": "We'd like a corporate account for bulk order pickups at our hotel",
        },
    )
    conversation_id = inbound.json()["conversation_id"]

    run_result = await client.post(
        f"/api/admin/conversations/{conversation_id}/run-agent", headers=admin_headers
    )
    body = run_result.json()
    assert body["decision"] == "escalate"
    assert body["order_id"] is None


@pytest.mark.asyncio
async def test_ordinary_pickup_request_still_creates_order(client, admin_headers):
    inbound = await client.post(
        "/api/mock-whatsapp/inbound",
        json={
            "market_code": "AE",
            "phone_number": "+971500000073",
            "message": "I need a wash and fold pickup tomorrow morning near Marina",
        },
    )
    conversation_id = inbound.json()["conversation_id"]

    run_result = await client.post(
        f"/api/admin/conversations/{conversation_id}/run-agent", headers=admin_headers
    )
    body = run_result.json()
    assert body["decision"] == "create_order"
    assert body["order_id"] is not None
