async def test_webhook_verification_success(client):
    response = await client.get(
        "/webhooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "test-verify-token",
            "hub.challenge": "12345",
        },
    )
    assert response.status_code == 200
    assert response.text == "12345"


async def test_webhook_verification_wrong_token(client):
    response = await client.get(
        "/webhooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong-token",
            "hub.challenge": "12345",
        },
    )
    assert response.status_code == 403


async def test_webhook_receives_and_stores_message_in_mock_mode(client):
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "from": "971501234567",
                                    "id": "wamid.test123",
                                    "type": "text",
                                    "text": {"body": "I need laundry pickup tomorrow"},
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }
    response = await client.post("/webhooks/whatsapp", json=payload)
    assert response.status_code == 200
    assert response.json()["processed"] == 1
