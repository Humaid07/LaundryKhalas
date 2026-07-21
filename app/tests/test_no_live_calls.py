import pytest

from app.llm.providers.anthropic_stub import AnthropicProviderStub
from app.llm.providers.base import LLMMessage
from app.llm.providers.openai_stub import OpenAIProviderStub
from app.llm.service import _select_provider
from app.llm.providers.mock import MockProvider


def test_default_provider_is_mock():
    assert isinstance(_select_provider(), MockProvider)


@pytest.mark.asyncio
async def test_anthropic_stub_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        await AnthropicProviderStub().complete([LLMMessage(role="user", content="hi")])


@pytest.mark.asyncio
async def test_openai_stub_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        await OpenAIProviderStub().complete([LLMMessage(role="user", content="hi")])
