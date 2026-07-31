"""Cache-aware LLM message assembly for the WhatsApp runtime.

ONE place that lays out a turn's messages so the Anthropic prompt cache actually
hits (spec 2026-07-31 — mixed 1h stable + 5m conversation cache):

  [ tools (1h) ]  ← rendered before system by the API; cached by the provider
  [ system: stable prompt (1h) ]
  [ history turns … (5m breakpoint on the last one) ]
  [ FINAL user turn: dynamic backend state + newest customer message ]  ← uncached

Everything before the last breakpoint must be byte-identical across turns for the
cache to read, so ALL per-turn/per-customer dynamic content (current date, persona
name, order state, prices, the newest message) goes into the FINAL user turn, which
sits after every breakpoint. Placing dynamic state as a system block instead would
render it BEFORE the history and silently kill the 5-minute conversation cache.

This module only arranges strings into ``LLMMessage`` objects; it makes no LLM call
and holds no business logic, so it is trivially unit-testable.
"""
from __future__ import annotations

from llm.providers.base import LLMMessage


def build_cached_messages(
    *,
    system_prompt: str,
    history: list[tuple[str, str]],
    dynamic_state: str | None,
    user_text: str,
    history_cache_ttl: str = "5m",
) -> list[LLMMessage]:
    """Assemble the messages for one WhatsApp turn with cache breakpoints placed.

    ``history`` is oldest-first ``(role, content)`` where role is "customer"/"agent".
    ``dynamic_state`` is optional per-turn backend context (JSON/text) that MUST NOT
    be cached; it is folded into the final user turn along with ``user_text``.
    """
    messages: list[LLMMessage] = [
        LLMMessage(role="system", content=system_prompt, cache="1h"),
    ]
    for role, content in history:
        messages.append(
            LLMMessage(role="user" if role == "customer" else "assistant", content=content)
        )
    # 5-minute breakpoint on the last history turn = the reusable conversation prefix.
    # Refreshed on every successful reuse, so an active chat keeps hitting it well past
    # five wall-clock minutes; only a >5-minute gap lets it expire (the 1h system cache
    # and the DB-authoritative state both survive that gap).
    if len(messages) > 1:
        messages[-1].cache = history_cache_ttl

    final = user_text
    if dynamic_state:
        final = f"{dynamic_state}\n\nCustomer message:\n{user_text}"
    messages.append(LLMMessage(role="user", content=final))
    return messages
