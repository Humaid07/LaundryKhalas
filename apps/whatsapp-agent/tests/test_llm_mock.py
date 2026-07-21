from llm import service as llm_service
from llm.providers.base import LLMMessage
from llm.providers.mock import MockProvider


async def test_mock_provider_returns_text_without_network():
    provider = MockProvider()
    result = await provider.complete([LLMMessage(role="user", content="hello")])
    assert result.provider == "mock"
    assert result.text


async def test_llm_service_defaults_to_mock_when_no_key_configured():
    result, latency_ms, success, error = await llm_service.complete(
        [LLMMessage(role="system", content="test"), LLMMessage(role="user", content="hi")]
    )
    assert result.provider == "mock"
    assert success is True
    assert error is None
    assert latency_ms >= 0
