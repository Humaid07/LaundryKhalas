import pytest


async def _create_pending_reply_approval(client, admin_headers, phone_number: str) -> str:
    inbound = await client.post(
        "/api/mock-whatsapp/inbound",
        json={
            "market_code": "AE",
            "phone_number": phone_number,
            "message": "I need laundry pickup tomorrow",
        },
    )
    conversation_id = inbound.json()["conversation_id"]
    run_result = await client.post(
        f"/api/admin/conversations/{conversation_id}/run-agent", headers=admin_headers
    )
    return run_result.json()["approval_id"], conversation_id


@pytest.mark.asyncio
async def test_approve_sends_mock_outbound_message(client, admin_headers):
    approval_id, conversation_id = await _create_pending_reply_approval(
        client, admin_headers, "+971500000020"
    )

    response = await client.post(
        f"/api/admin/approvals/{approval_id}/approve",
        json={"decided_by": "test_admin"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "approved"
    assert body["approved_by"] == "test_admin"

    messages = await client.get(
        f"/api/admin/conversations/{conversation_id}/messages", headers=admin_headers
    )
    outbound = [m for m in messages.json() if m["direction"] == "outbound"]
    assert len(outbound) == 1
    assert outbound[0]["status"] == "mock_sent"


@pytest.mark.asyncio
async def test_reject_marks_rejected_without_sending(client, admin_headers):
    approval_id, conversation_id = await _create_pending_reply_approval(
        client, admin_headers, "+971500000021"
    )

    response = await client.post(
        f"/api/admin/approvals/{approval_id}/reject",
        json={"decided_by": "test_admin", "decision_note": "not needed"},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"

    messages = await client.get(
        f"/api/admin/conversations/{conversation_id}/messages", headers=admin_headers
    )
    outbound = [m for m in messages.json() if m["direction"] == "outbound"]
    assert len(outbound) == 0


@pytest.mark.asyncio
async def test_approving_twice_fails(client, admin_headers):
    approval_id, _ = await _create_pending_reply_approval(client, admin_headers, "+971500000022")

    first = await client.post(
        f"/api/admin/approvals/{approval_id}/approve",
        json={"decided_by": "test_admin"},
        headers=admin_headers,
    )
    assert first.status_code == 200

    second = await client.post(
        f"/api/admin/approvals/{approval_id}/approve",
        json={"decided_by": "test_admin"},
        headers=admin_headers,
    )
    assert second.status_code == 409
