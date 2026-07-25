"""/health/ai readiness endpoint — safe status, no key, no paid call."""


async def test_health_ai_reports_safe_status(client):
    resp = await client.get("/health/ai")
    assert resp.status_code == 200
    body = resp.json()
    # In the test env AI_PROVIDER resolves to mock (conftest forces it).
    assert body["provider"] == "mock"
    assert set(body) >= {"provider", "enabled", "configured", "model_configured",
                         "tool_use_enabled", "live_ready"}
    # never leak the key (no key field, no key value anywhere)
    assert "sk-" not in resp.text
    assert "api_key" not in resp.text.lower()
