"""Scripted, offline fake of the AsyncAnthropic client for provider tests.

Records every ``messages.create`` kwargs into ``client.messages.calls`` and returns
the next scripted response — no key, no network. Shared by the model-selection and
prompt-cache-structure suites.
"""
from __future__ import annotations


class Block:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class Usage:
    def __init__(self, i=0, o=0, cr=0, cw=0, *, cw5=None, cw1=None):
        self.input_tokens = i
        self.output_tokens = o
        self.cache_read_input_tokens = cr
        self.cache_creation_input_tokens = cw
        # Per-TTL split (present since the extended-cache beta). Only attached when
        # provided so tests can also exercise the "field absent" path.
        if cw5 is not None or cw1 is not None:
            self.cache_creation = {
                "ephemeral_5m_input_tokens": cw5 or 0,
                "ephemeral_1h_input_tokens": cw1 or 0,
            }


class Resp:
    def __init__(self, content, stop_reason, usage):
        self.content = content
        self.stop_reason = stop_reason
        self.usage = usage


class _FakeMessages:
    def __init__(self, script):
        self._script = list(script)
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._script.pop(0)


class FakeClient:
    def __init__(self, script):
        self.messages = _FakeMessages(script)


def text(t: str) -> Block:
    return Block(type="text", text=t)


def tool_use(name: str, tool_input: dict, id: str = "t1") -> Block:
    return Block(type="tool_use", name=name, input=tool_input, id=id)
