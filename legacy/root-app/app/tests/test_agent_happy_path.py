import uuid

import pytest
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.order import Order


@pytest.mark.asyncio
async def test_agent_asks_followup_when_info_incomplete(client, admin_headers):
    inbound = await client.post(
        "/api/mock-whatsapp/inbound",
        json={
            "market_code": "AE",
            "phone_number": "+971500000010",
            "customer_name": "Incomplete Info",
            "message": "I need laundry pickup tomorrow",
        },
    )
    conversation_id = inbound.json()["conversation_id"]

    run_result = await client.post(
        f"/api/admin/conversations/{conversation_id}/run-agent", headers=admin_headers
    )
    assert run_result.status_code == 200
    body = run_result.json()
    assert body["decision"] == "ask_followup"
    assert body["order_id"] is None
    assert body["approval_id"] is not None
    assert "area" in body["draft_reply_text"].lower() or "pickup" in body["draft_reply_text"].lower()


@pytest.mark.asyncio
async def test_agent_creates_order_when_info_complete(client, admin_headers):
    inbound = await client.post(
        "/api/mock-whatsapp/inbound",
        json={
            "market_code": "AE",
            "phone_number": "+971500000011",
            "customer_name": "Complete Info",
            "message": "I need a wash and fold pickup tomorrow morning near Marina",
        },
    )
    conversation_id = inbound.json()["conversation_id"]

    run_result = await client.post(
        f"/api/admin/conversations/{conversation_id}/run-agent", headers=admin_headers
    )
    assert run_result.status_code == 200
    body = run_result.json()
    assert body["decision"] == "create_order"
    assert body["order_id"] is not None
    assert body["approval_id"] is not None

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Order).where(Order.id == uuid.UUID(body["order_id"])))
        order = result.scalar_one()
        assert order.status == "created"
        assert order.facility_id is not None
        assert order.estimated_total is not None

    events_response = await client.get(
        f"/api/admin/orders/{body['order_id']}/events", headers=admin_headers
    )
    assert events_response.status_code == 200
    event_types = {e["event_type"] for e in events_response.json()}
    assert "order_drafted" in event_types
    assert "status_change" in event_types
    assert "facility_assigned" in event_types

    logs_by_order = await client.get(
        "/api/admin/ai-action-logs",
        params={"order_id": body["order_id"]},
        headers=admin_headers,
    )
    assert logs_by_order.status_code == 200
    assert len(logs_by_order.json()) > 0


@pytest.mark.asyncio
async def test_run_agent_requires_admin_key(client):
    inbound = await client.post(
        "/api/mock-whatsapp/inbound",
        json={"market_code": "AE", "phone_number": "+971500000012", "message": "hello"},
    )
    conversation_id = inbound.json()["conversation_id"]

    response = await client.post(f"/api/admin/conversations/{conversation_id}/run-agent")
    assert response.status_code == 401
