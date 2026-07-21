import uuid

import pytest
from sqlalchemy import select

from app.agents.classifier.agent import (
    ClassifierConversationNotFound,
    NoInboundMessageToClassify,
    classifier_agent,
)
from app.db.session import AsyncSessionLocal
from app.models.conversation import Conversation
from app.models.customer import Customer
from app.models.market import Market


@pytest.mark.asyncio
async def test_classifier_runs_automatically_on_inbound(client, admin_headers):
    inbound = await client.post(
        "/api/mock-whatsapp/inbound",
        json={
            "market_code": "AE",
            "phone_number": "+971500000060",
            "customer_name": "Classifier Test",
            "message": "I need laundry pickup tomorrow near Marina",
        },
    )
    assert inbound.status_code == 200
    conversation_id = inbound.json()["conversation_id"]

    conv = await client.get(f"/api/admin/conversations/{conversation_id}", headers=admin_headers)
    assert conv.status_code == 200
    body = conv.json()
    assert body["latest_intent"] == "order_placement"
    assert body["latest_sentiment"] == "neutral"
    assert body["latest_urgency"] == "normal"


@pytest.mark.asyncio
async def test_classifier_detects_angry_complaint(client, admin_headers):
    inbound = await client.post(
        "/api/mock-whatsapp/inbound",
        json={
            "market_code": "AE",
            "phone_number": "+971500000061",
            "message": "This is unacceptable, my clothes are ruined!",
        },
    )
    conversation_id = inbound.json()["conversation_id"]

    conv = await client.get(f"/api/admin/conversations/{conversation_id}", headers=admin_headers)
    body = conv.json()
    assert body["latest_intent"] == "facility_issue"
    assert body["latest_sentiment"] == "angry"
    assert body["latest_urgency"] == "urgent"

    logs = await client.get(
        "/api/admin/ai-action-logs",
        params={"conversation_id": conversation_id},
        headers=admin_headers,
    )
    classify_rows = [r for r in logs.json() if r["action_type"] == "classify"]
    assert len(classify_rows) == 1
    output = classify_rows[0]["output_json"]
    assert output["complaint_flag"] is True
    assert output["angry_flag"] is True
    assert output["is_urgent"] is True
    assert output["is_escalated"] is True
    assert classify_rows[0]["agent_name"] == "classifier_agent"


@pytest.mark.asyncio
async def test_classifier_detects_b2b_lead(client, admin_headers):
    inbound = await client.post(
        "/api/mock-whatsapp/inbound",
        json={
            "market_code": "AE",
            "phone_number": "+971500000062",
            "message": "We'd like a corporate account for bulk order pickups at our hotel",
        },
    )
    conversation_id = inbound.json()["conversation_id"]

    conv = await client.get(f"/api/admin/conversations/{conversation_id}", headers=admin_headers)
    body = conv.json()
    assert body["latest_intent"] == "b2b_lead"

    logs = await client.get(
        "/api/admin/ai-action-logs",
        params={"conversation_id": conversation_id},
        headers=admin_headers,
    )
    output = next(r["output_json"] for r in logs.json() if r["action_type"] == "classify")
    assert output["b2b_enquiry_detected"] is True
    assert output["needs_followup"] is True


@pytest.mark.asyncio
async def test_classifier_detects_cancellation(client, admin_headers):
    inbound = await client.post(
        "/api/mock-whatsapp/inbound",
        json={
            "market_code": "AE",
            "phone_number": "+971500000063",
            "message": "I want to cancel my order please",
        },
    )
    conversation_id = inbound.json()["conversation_id"]

    logs = await client.get(
        "/api/admin/ai-action-logs",
        params={"conversation_id": conversation_id},
        headers=admin_headers,
    )
    output = next(r["output_json"] for r in logs.json() if r["action_type"] == "classify")
    assert output["intent"] == "cancellation"
    assert output["refund_or_cancellation_detected"] is True
    assert output["sales_stage_delta"] == "lost"


@pytest.mark.asyncio
async def test_manual_classify_endpoint_reclassifies(client, admin_headers):
    inbound = await client.post(
        "/api/mock-whatsapp/inbound",
        json={"market_code": "AE", "phone_number": "+971500000064", "message": "hello"},
    )
    conversation_id = inbound.json()["conversation_id"]

    response = await client.post(
        f"/api/admin/conversations/{conversation_id}/classify", headers=admin_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert "intent" in body and "sentiment" in body and "is_urgent" in body


@pytest.mark.asyncio
async def test_classify_requires_admin_key(client):
    inbound = await client.post(
        "/api/mock-whatsapp/inbound",
        json={"market_code": "AE", "phone_number": "+971500000065", "message": "hello"},
    )
    conversation_id = inbound.json()["conversation_id"]

    response = await client.post(f"/api/admin/conversations/{conversation_id}/classify")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_classify_unknown_conversation_returns_404(client, admin_headers):
    response = await client.post(
        f"/api/admin/conversations/{uuid.uuid4()}/classify", headers=admin_headers
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_classify_conversation_with_no_messages_raises(ae_market_id):
    async with AsyncSessionLocal() as db:
        market_result = await db.execute(select(Market).where(Market.id == ae_market_id))
        market = market_result.scalar_one()
        customer = Customer(market_id=market.id, phone_number="+971500000099")
        db.add(customer)
        await db.flush()
        conversation = Conversation(market_id=market.id, customer_id=customer.id, channel="whatsapp")
        db.add(conversation)
        await db.commit()
        conversation_id = conversation.id

    async with AsyncSessionLocal() as db:
        with pytest.raises(NoInboundMessageToClassify):
            await classifier_agent.classify(db, conversation_id=conversation_id)


@pytest.mark.asyncio
async def test_classify_missing_conversation_raises():
    async with AsyncSessionLocal() as db:
        with pytest.raises(ClassifierConversationNotFound):
            await classifier_agent.classify(db, conversation_id=uuid.uuid4())
