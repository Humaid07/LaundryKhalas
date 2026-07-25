"""Application-controlled retry behaviour in AnthropicProvider._create.

Transient errors retry with bounded backoff; non-retryable errors propagate
immediately (so the service layer can fall back to the safe mock). Offline —
no network, sleeps are patched out.
"""
import httpx
import pytest
from anthropic import APIConnectionError, APITimeoutError

from llm.providers import anthropic as anth
from llm.providers.anthropic import AnthropicProvider, _is_retryable
from llm.providers.base import LLMMessage


class _Usage:
    input_tokens = 5
    output_tokens = 5
    cache_read_input_tokens = 0
    cache_creation_input_tokens = 0


class _Resp:
    stop_reason = "end_turn"
    usage = _Usage()
    _request_id = "req_test"

    class _T:
        type = "text"
        text = "OK"

    content = [_T()]


class _FlakyMessages:
    def __init__(self, fail_times, error):
        self._fail_times = fail_times
        self._error = error
        self.attempts = 0

    async def create(self, **kwargs):
        self.attempts += 1
        if self.attempts <= self._fail_times:
            raise self._error
        return _Resp()


class _FlakyClient:
    def __init__(self, fail_times, error):
        self.messages = _FlakyMessages(fail_times, error)


def _timeout_err():
    return APITimeoutError(request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))


def test_is_retryable_classification():
    assert _is_retryable(_timeout_err()) is True
    assert _is_retryable(APIConnectionError(request=httpx.Request("POST", "https://x"))) is True
    assert _is_retryable(ValueError("bad input")) is False  # non-retryable proxy (auth/validation)


async def test_retries_then_succeeds(monkeypatch):
    slept = []

    async def _fake_sleep(d):
        slept.append(d)

    monkeypatch.setattr(anth.asyncio, "sleep", _fake_sleep)
    client = _FlakyClient(fail_times=2, error=_timeout_err())
    provider = AnthropicProvider("k", "claude-opus-4-8", client=client, max_retries=3)

    result = await provider.complete([LLMMessage(role="user", content="hi")])
    assert result.text == "OK"
    assert client.messages.attempts == 3   # 2 failures + 1 success
    assert len(slept) == 2                  # backed off twice
    assert all(d > 0 for d in slept)        # bounded positive delays


async def test_gives_up_after_max_retries(monkeypatch):
    async def _fake_sleep(d):
        pass

    monkeypatch.setattr(anth.asyncio, "sleep", _fake_sleep)
    client = _FlakyClient(fail_times=99, error=_timeout_err())
    provider = AnthropicProvider("k", "claude-opus-4-8", client=client, max_retries=2)

    with pytest.raises(APITimeoutError):
        await provider.complete([LLMMessage(role="user", content="hi")])
    assert client.messages.attempts == 3    # initial + 2 retries


async def test_non_retryable_not_retried(monkeypatch):
    async def _fake_sleep(d):  # pragma: no cover - must never be called
        raise AssertionError("should not sleep on non-retryable error")

    monkeypatch.setattr(anth.asyncio, "sleep", _fake_sleep)
    client = _FlakyClient(fail_times=99, error=ValueError("nope"))
    provider = AnthropicProvider("k", "claude-opus-4-8", client=client, max_retries=3)

    with pytest.raises(ValueError):
        await provider.complete([LLMMessage(role="user", content="hi")])
    assert client.messages.attempts == 1    # no retry
