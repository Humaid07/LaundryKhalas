"""Protected Anthropic connectivity smoke test.

Run this MANUALLY after configuring the key to confirm real connectivity —
health endpoints never make a billed call, this one does (a single, tiny
request). It validates configuration, sends a minimal Messages API request,
and prints the model, latency, token usage and request id.

  python -m scripts.test_anthropic
  python scripts/test_anthropic.py

Exit code 0 on success, non-zero on any failure. NEVER prints the API key.
"""
from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

# Allow running as a plain script (python scripts/test_anthropic.py).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from llm.providers.base import LLMMessage  # noqa: E402
from settings import get_settings  # noqa: E402


async def _run() -> int:
    settings = get_settings()

    # 1) Validate configuration (fails safe, never leaks the key).
    try:
        settings.validate_ai_config()
    except ValueError as exc:
        print(f"[FAIL] Invalid AI configuration: {exc}")
        return 2

    if settings.ai_provider_effective != "anthropic":
        print(f"[SKIP] AI_PROVIDER is '{settings.ai_provider_effective}', not 'anthropic'. "
              "Set AI_PROVIDER=anthropic (or LLM_PROVIDER=anthropic) to smoke-test Claude.")
        return 3
    if not settings.live_llm_ready:
        print("[FAIL] Anthropic is not live-ready (disabled or missing key).")
        return 4

    key = settings.anthropic_api_key
    print("Provider     : anthropic")
    print(f"Model        : {settings.anthropic_model_effective}")
    print(f"API key      : configured (len={len(key)}, prefix={key[:7]}…)")
    print(f"Timeout      : {settings.anthropic_timeout_seconds}s | "
          f"app retries: {settings.anthropic_max_retries}")
    print("Sending a minimal request…")

    # 2) Send a minimal real request through the same provider the agent uses.
    from llm.providers.anthropic import AnthropicProvider

    provider = AnthropicProvider(
        key,
        settings.anthropic_model_effective,
        timeout_seconds=settings.anthropic_timeout_seconds,
        max_retries=settings.anthropic_max_retries,
        max_tokens=32,
    )
    start = time.perf_counter()
    try:
        result = await provider.complete(
            [LLMMessage(role="user", content="Reply with the single word: OK")],
            max_tokens=16,
        )
    except Exception as exc:  # noqa: BLE001 - surface any connectivity failure
        # Guard against a key accidentally appearing in an error string.
        msg = str(exc).replace(key, "***REDACTED***") if key else str(exc)
        print(f"[FAIL] Anthropic request failed: {type(exc).__name__}: {msg}")
        return 5
    latency_ms = (time.perf_counter() - start) * 1000

    # 3) Confirm a usable response.
    if not result.text:
        print("[FAIL] Empty response from Anthropic.")
        return 6

    print("\n[OK] Anthropic connectivity confirmed.")
    print(f"  reply     : {result.text!r}")
    print(f"  model     : {result.model}")
    print(f"  latency   : {latency_ms:.0f} ms")
    print(f"  tokens    : in={result.tokens_in} out={result.tokens_out} "
          f"cache_read={result.cache_read_tokens} cache_write={result.cache_write_tokens}")
    print(f"  est. cost : ${result.cost_usd:.5f}")
    print(f"  request_id: {result.request_id}")
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_run()))


if __name__ == "__main__":
    main()
