import pytest


@pytest.mark.asyncio
async def test_agent_run_creates_ai_action_logs(client, admin_headers):
    inbound = await client.post(
        "/api/mock-whatsapp/inbound",
        json={
            "market_code": "AE",
            "phone_number": "+971500000040",
            "message": "I need a wash and fold pickup tomorrow morning near Marina",
        },
    )
    conversation_id = inbound.json()["conversation_id"]

    await client.post(
        f"/api/admin/conversations/{conversation_id}/run-agent", headers=admin_headers
    )

    logs_response = await client.get(
        "/api/admin/ai-action-logs",
        params={"conversation_id": conversation_id},
        headers=admin_headers,
    )
    assert logs_response.status_code == 200
    logs = logs_response.json()
    assert len(logs) > 0

    action_types = {log["action_type"] for log in logs}
    assert "agent_run" in action_types
    assert "tool_call" in action_types
    assert "llm_complete" in action_types

    tool_names = {log["tool_name"] for log in logs if log["tool_name"]}
    assert "create_order" in tool_names
    assert "assign_facility_to_order" in tool_names
    assert "draft_customer_reply" in tool_names
