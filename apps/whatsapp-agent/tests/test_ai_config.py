"""AI provider configuration + fail-safe startup validation (settings.py).

Verifies the mock-first gate, the spec-name/legacy-name fallback, and that
validation fails safely without ever leaking the API key.
"""
import pytest

from settings import DEFAULT_ANTHROPIC_MODEL, Settings


def _s(**kw) -> Settings:
    # _env_file=None → ignore any real .env so these are hermetic.
    return Settings(_env_file=None, **kw)


def test_default_is_mock_and_not_live():
    s = _s()
    assert s.ai_provider_effective == "mock"
    assert s.live_llm_ready is False
    s.validate_ai_config()  # must not raise in mock mode


def test_anthropic_ready_when_enabled_with_key():
    s = _s(ai_provider="anthropic", anthropic_api_key="sk-ant-secret")
    assert s.live_llm_ready is True
    assert s.anthropic_model_effective == DEFAULT_ANTHROPIC_MODEL
    s.validate_ai_config()


def test_legacy_llm_provider_still_works():
    # AI_PROVIDER blank → falls back to LLM_PROVIDER; LLM_MODEL → model.
    s = _s(llm_provider="anthropic", llm_model="claude-sonnet-5", anthropic_api_key="k")
    assert s.ai_provider_effective == "anthropic"
    assert s.anthropic_model_effective == "claude-sonnet-5"
    assert s.live_llm_ready is True


def test_enabled_without_key_fails_safely_and_hides_key():
    s = _s(ai_provider="anthropic", anthropic_api_key="")
    with pytest.raises(ValueError) as exc:
        s.validate_ai_config()
    assert "ANTHROPIC_API_KEY" in str(exc.value)
    assert "sk-" not in str(exc.value)  # never echo a key


def test_disabled_provider_is_not_live_and_never_calls():
    s = _s(ai_provider="anthropic", anthropic_api_key="k", anthropic_enabled=False)
    assert s.live_llm_ready is False
    s.validate_ai_config()  # disabled → nothing to validate, no raise


@pytest.mark.parametrize("field,value,token", [
    ("anthropic_max_tokens", 0, "MAX_TOKENS"),
    ("anthropic_timeout_seconds", 0, "TIMEOUT"),
    ("anthropic_max_retries", 99, "MAX_RETRIES"),
    ("anthropic_max_tool_rounds", 0, "MAX_TOOL_ROUNDS"),
    ("anthropic_temperature", 5.0, "TEMPERATURE"),
])
def test_invalid_numeric_config_rejected(field, value, token):
    s = _s(ai_provider="anthropic", anthropic_api_key="k", **{field: value})
    with pytest.raises(ValueError) as exc:
        s.validate_ai_config()
    assert token in str(exc.value)


def test_ai_status_never_contains_the_key():
    s = _s(ai_provider="anthropic", anthropic_api_key="sk-ant-supersecret", llm_model="claude-sonnet-5")
    status = s.ai_status
    assert status["provider"] == "anthropic"
    assert status["configured"] is True          # a key IS set…
    assert status["model"] == "claude-sonnet-5"
    # …but the key value never appears anywhere in the status payload
    assert "sk-ant-supersecret" not in str(status)
    assert "key" not in {k.lower() for k in status} or "api_key" not in str(status).lower()
