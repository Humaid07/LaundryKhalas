async def test_settings_status(client):
    response = await client.get("/api/settings/status")
    assert response.status_code == 200
    body = response.json()
    assert body["llm_provider"] == "mock"
    assert body["llm_live_ready"] is False
    assert body["whatsapp_mode"] == "mock"
    assert body["whatsapp_live_ready"] is False
    assert body["database_kind"] == "sqlite"
    assert "anthropic_api_key" not in body
    assert "meta_whatsapp_access_token" not in body
