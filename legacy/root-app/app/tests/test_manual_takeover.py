import pytest


@pytest.mark.asyncio
async def test_manual_takeover_blocks_agent_run(client, admin_headers):
    inbound = await client.post(
        "/api/mock-whatsapp/inbound",
        json={
            "market_code": "AE",
            "phone_number": "+971500000030",
            "message": "I need laundry pickup tomorrow",
        },
    )
    conversation_id = inbound.json()["conversation_id"]

    takeover = await client.post(
        f"/api/admin/conversations/{conversation_id}/manual-takeover",
        json={"taken_over_by": "agent_smith"},
        headers=admin_headers,
    )
    assert takeover.status_code == 200
    assert takeover.json()["manual_takeover"] is True

    run_result = await client.post(
        f"/api/admin/conversations/{conversation_id}/run-agent", headers=admin_headers
    )
    assert run_result.status_code == 409

    approvals = await client.get("/api/admin/approvals", headers=admin_headers)
    matching = [a for a in approvals.json() if a["conversation_id"] == conversation_id]
    assert matching == []


@pytest.mark.asyncio
async def test_release_takeover_allows_agent_run_again(client, admin_headers):
    inbound = await client.post(
        "/api/mock-whatsapp/inbound",
        json={
            "market_code": "AE",
            "phone_number": "+971500000031",
            "message": "I need laundry pickup tomorrow",
        },
    )
    conversation_id = inbound.json()["conversation_id"]

    await client.post(
        f"/api/admin/conversations/{conversation_id}/manual-takeover",
        json={"taken_over_by": "agent_smith"},
        headers=admin_headers,
    )
    await client.post(
        f"/api/admin/conversations/{conversation_id}/release-takeover", headers=admin_headers
    )

    run_result = await client.post(
        f"/api/admin/conversations/{conversation_id}/run-agent", headers=admin_headers
    )
    assert run_result.status_code == 200
