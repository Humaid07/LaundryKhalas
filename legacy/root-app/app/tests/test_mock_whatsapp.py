import pytest
from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.conversation import Conversation
from app.models.customer import Customer
from app.models.message import Message


@pytest.mark.asyncio
async def test_inbound_creates_customer_conversation_message(client):
    response = await client.post(
        "/api/mock-whatsapp/inbound",
        json={
            "market_code": "AE",
            "phone_number": "+971500000001",
            "customer_name": "Test Customer",
            "message": "I need laundry pickup tomorrow",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert "conversation_id" in body
    assert "message_id" in body
    assert "customer_id" in body

    async with AsyncSessionLocal() as db:
        cust_result = await db.execute(
            select(Customer).where(Customer.phone_number == "+971500000001")
        )
        customer = cust_result.scalar_one()
        assert customer.name == "Test Customer"

        conv_result = await db.execute(
            select(Conversation).where(Conversation.customer_id == customer.id)
        )
        conversation = conv_result.scalar_one()
        assert conversation.status == "open"

        msg_result = await db.execute(
            select(Message).where(Message.conversation_id == conversation.id)
        )
        message = msg_result.scalar_one()
        assert message.direction == "inbound"
        assert message.text == "I need laundry pickup tomorrow"


@pytest.mark.asyncio
async def test_outbound_stores_mock_sent_message(client):
    inbound = await client.post(
        "/api/mock-whatsapp/inbound",
        json={
            "market_code": "AE",
            "phone_number": "+971500000002",
            "message": "hello",
        },
    )
    conversation_id = inbound.json()["conversation_id"]

    response = await client.post(
        "/api/mock-whatsapp/outbound",
        json={"conversation_id": conversation_id, "message": "Your pickup is confirmed."},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "mock_sent"
