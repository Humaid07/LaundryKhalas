# Build Report — Connect the WhatsApp Agent to Anthropic Claude

**Date:** 2026-07-25
**Author:** Engineering (Claude Code session)
**Status:** ✅ Implemented, tested, and verified live against the real Anthropic API.

---

## 1. Build title
Integrate Anthropic Claude (tool-use) into the live WhatsApp Operations Agent so customer messages are understood and answered naturally — **without** replacing the deterministic booking workflow, pricing, SLA, or authorization logic.

## 2. Date
2026-07-25.

## 3. Task objective
Wire real Claude language understanding into the existing agent so that, on the non-booking conversational path, the model answers with **grounded** figures (prices, turnaround, coverage) pulled from the deterministic engines via backend-validated tools. Booking stays a deterministic state machine; Claude only improves NLU + phrasing.

## 4. What was built
- **Tool-use agentic loop** in the existing `AnthropicProvider` (no new/parallel agent). Claude can request read-only backend tools; the backend validates + executes each against the deterministic engines and feeds results back until Claude produces the final reply.
- **A grounded tool layer** (`llm_tools.py`) exposing 4 read-only tools over the catalogue/pricing, delivery-SLA, and area-gazetteer engines. Tools never invent data and reject bad/unknown input safely; every call is logged.
- **Prompt caching** of the (large, stable) system prompt + tool set → ~90% cheaper on the cached prefix for repeat turns.
- **Token + estimated-cost tracking** (`llm/costs.py`), persisted as message metadata and structured logs (satisfies "every agent/tool action is logged").
- **Provider stays mock-first**: nothing goes live unless `LLM_PROVIDER=anthropic` **and** `ANTHROPIC_API_KEY` is present (`settings.live_llm_ready`). Mock remains the default and the safe fallback on any failure.

## 5. Why it was built
The active backend already had a clean LLM seam (`llm/service.py` → `AnthropicProvider`) and the `anthropic` dependency, but the provider was **text-only** (no tool use), used a **wrong date-suffixed model id**, had **no caching** and **no cost tracking**. The task required Claude to understand requests and call backend tools while the deterministic booking/pricing/SLA/auth logic stayed authoritative. Extending the existing seam (rather than adding a second agent) was the correct, low-risk path per the audit.

## 6. Files created
- `apps/whatsapp-agent/llm/costs.py` — per-model USD price table + `estimate_cost_usd()` (input/output/cache buckets).
- `apps/whatsapp-agent/agents/whatsapp_agent/llm_tools.py` — Anthropic tool schemas + validated, logged `execute_tool()` executor over the deterministic engines.
- `apps/whatsapp-agent/tests/test_llm_tools.py` — 13 tests: grounded/ambiguous/none/measured/firm price, categories, turnaround, area, bad input, unknown tool.
- `apps/whatsapp-agent/tests/test_anthropic_tool_loop.py` — 8 tests: tool loop against a scripted fake client, caching, usage/cost, non-convergence → raise, service-layer safe fallback, mock-mode-ignores-tools.
- `docs/build-reports/2026-07-25-anthropic-claude-integration.md` — this report.

## 7. Files modified
- `apps/whatsapp-agent/llm/providers/base.py` — `ToolCall` dataclass, richer `LLMResult` (cache tokens, `stop_reason`, `tool_calls`, `cost_usd`), `ToolExecutor` type, default `complete_with_tools()` that falls back to `complete()` (keeps mock/OpenAI unchanged).
- `apps/whatsapp-agent/llm/providers/anthropic.py` — full rewrite: correct default model `claude-opus-4-8` (overridable), system+tools prompt caching, cache-token capture, `complete_with_tools()` agentic loop, injectable client for offline tests, SDK retry (`max_retries=3`).
- `apps/whatsapp-agent/llm/service.py` — new `complete_with_tools()` wrapper (provider selection, latency, success, safe mock fallback).
- `apps/whatsapp-agent/agents/whatsapp_agent/agent.py` — non-booking path routes through `complete_with_tools` when live; `AgentReply` carries tokens/cost/tool_calls.
- `apps/whatsapp-agent/api/evolution_webhooks.py` — stores provider/model/tokens/cost/tool_calls in the outbound message metadata + structured log.
- `apps/whatsapp-agent/settings.py` — clarified `llm_model` comment (default + cost-lever guidance).
- `apps/whatsapp-agent/.env.example` — documented provider/key/model.
- `apps/whatsapp-agent/.env` — **local only, gitignored**: `LLM_PROVIDER=anthropic` + `ANTHROPIC_API_KEY` set to the operator-provided key. Never committed.

## 8. API endpoints added/changed
None. The inbound flow (`POST /webhooks/evolution`) and outbound send are unchanged; only the non-booking reply generation inside them now uses Claude when live.

## 9. Database tables/models added/changed
None. Token/cost/tool-call data is stored in the existing `messages.metadata` (jsonb) — no migration.

## 10. UI pages/components added/changed
None.

## 11. Agent behavior added/changed
- Non-booking questions (pricing / service list / turnaround / area coverage) are now answered by Claude **with grounded figures** obtained through backend tools, instead of the rule-based mock.
- Booking, escalation, domain-guard (layer 1), allow-list, idempotency, and the stateful order flows (track/cancel/change/add) still run **before** the LLM and are unchanged — Claude cannot reach a booking transition.
- On any LLM/tool failure the agent falls back to the deterministic mock reply — the reply path never crashes.

## 12. Integrations added/changed
Anthropic Claude via the official `anthropic` Python SDK (already a dependency, v0.117.0 in the venv), using native tool use + prompt caching.

## 13. What is mock-only
Everything by default. With `LLM_PROVIDER=mock` (default) the behaviour is byte-for-byte identical to before — the tool wiring is inert.

## 14. What is live
On this machine only: `LLM_PROVIDER=anthropic` + key are set in the gitignored `.env`, so the agent path calls the real API. Live WhatsApp send/receive still additionally requires `WHATSAPP_MODE=evolution` + the allow-list + operating mode (unchanged gates).

## 15. What is intentionally deferred
- Streaming responses (not needed for short WhatsApp replies).
- Using Claude for **booking-slot NLU** (booking remains the deterministic FSM by design).
- A dedicated AI-usage dashboard panel (data is now persisted in message metadata + logs; surfacing it in the UI is a follow-up).
- Migrating the parallel `laundry_class/` LangGraph experiment (untouched; still tests/scripts only).

## 16. Tests run
`./.venv/Scripts/python.exe -m pytest -q` (full suite) + the two new test files.

## 17. Test results
- Baseline before changes: **414 passed**.
- After changes: **435 passed** (414 + 21 new), 0 failures, ~110s. Suite stays hermetic (`conftest.py` forces `LLM_PROVIDER=mock` via `os.environ`, which outranks `.env`, so tests never hit the live API).

## 18. Bugs/issues found
- The pre-existing `AnthropicProvider` used a date-suffixed model id (`claude-haiku-4-5-20251001`) — corrected to a valid current default.

## 19. Known limitations
- **Cost:** `claude-opus-4-8` is ~$0.007–0.018 per message in the live smoke test. For high WhatsApp volume, set `LLM_MODEL=claude-haiku-4-5` to cut cost materially — left as a deliberate operator choice.
- Layer-1 keyword domain guard classifies some clearly off-topic questions as "uncertain" (they then go to the LLM, whose layer-2 guard refuses correctly). Defense-in-depth works; tightening layer 1 is a separate cleanup.

## 20. Security/privacy notes
- API key lives **only** in the gitignored `.env`; it is never committed, logged, echoed, or sent to the frontend. Verified: `.env` is untracked and the key string appears in no tracked file.
- ⚠️ **Rotate the key.** It was pasted into chat in plaintext, so it should be treated as exposed — revoke/rotate it in the Anthropic console after testing and replace the `.env` value.
- Privacy firewall unchanged: tools are grounded on catalogue/SLA/area config only; no customer PII is sent to build tool inputs.

## 21. Cost/LLM usage notes
Per-turn `tokens_in/out`, cache read/write, and an estimated USD cost are captured on every reply and persisted to `messages.metadata` + emitted in the `evolution_auto_reply_sent` log. Estimates use a static price table (`llm/costs.py`); the Anthropic console remains authoritative.

## 22. Screens/pages to demo
No new screens. Demo via the live smoke script output (below) or by messaging the connected test number once `WHATSAPP_MODE=evolution` is on.

## 23. Commands to run
```bash
cd "D:/Laundry Khalas App/apps/whatsapp-agent"
# tests (offline, hermetic)
./.venv/Scripts/python.exe -m pytest -q
# live smoke test of the Claude path (uses .env key — real, billed calls)
PYTHONUTF8=1 ./.venv/Scripts/python.exe <scratchpad>/live_smoke.py
```

## 24. How to verify manually
With `LLM_PROVIDER=anthropic` + key in `.env`, call `agents.whatsapp_agent.agent.handle_message(text=..., history=[], db=None)`:
- "How much to dry clean a suit?" → Claude calls `lookup_item_price` → grounded "AED 45 per item (excl. 5% VAT)".
- "How long does wash & fold take?" → `estimate_turnaround` → grounded SLA.
- "Do you pick up from Dubai Marina?" → `check_service_area` → grounded confirmation.
- "What's the capital of France?" → refused/redirected (domain guard).

Live smoke output (2026-07-25):
```
[pricing]    tools=['lookup_item_price']   in=400 out=110 cost=$0.00679
[turnaround] tools=['estimate_turnaround'] in=386 out=118 cost=$0.01838
[area]       tools=['check_service_area']  in=291 out=112 cost=$0.01777
[greeting]   tools=[]                      in=77  out=52  cost=$0.01393
[out-of-domain] refused/redirected         tools=[]
```

## 25. Next recommended step
1. Rotate the exposed API key.
2. Decide production model tier (`claude-opus-4-8` vs `claude-sonnet-5` vs `claude-haiku-4-5`) based on the cost/quality tradeoff.
3. Optionally surface the persisted AI-usage/cost metadata in the Operations dashboard.
4. Consider running the agent live on WhatsApp (`WHATSAPP_MODE=evolution`, allow-list) to test the full inbound→Claude→outbound loop.

---

## Phase 2 (2026-07-25) — production hardening from the detailed spec

Follow-up increment implementing the safe, high-value gaps from the expanded integration spec, **without** re-architecting the deterministic booking FSM.

**Added / changed**
- **Config surface + fail-safe startup validation** (`settings.py`): `AI_PROVIDER`, `ANTHROPIC_ENABLED`, `ANTHROPIC_MODEL`, `ANTHROPIC_MAX_TOKENS`, `ANTHROPIC_TEMPERATURE`, `ANTHROPIC_TIMEOUT_SECONDS`, `ANTHROPIC_MAX_RETRIES`, `ANTHROPIC_TOOL_USE_ENABLED`, `ANTHROPIC_LOG_USAGE`, `ANTHROPIC_STORE_RAW_CONTENT`, `ANTHROPIC_MAX_TOOL_ROUNDS`, `ANTHROPIC_HISTORY_MESSAGE_LIMIT`, `ANTHROPIC_HISTORY_CHARACTER_LIMIT`. Spec names fall back to legacy `LLM_PROVIDER`/`LLM_MODEL` (backward compatible). `validate_ai_config()` runs at startup (`main.py` lifespan) and fails safely on enabled-but-no-key / empty model / out-of-range numbers — **never echoing the key**.
- **Singleton provider/client** (`llm/service.py`): one cached `AnthropicProvider` per (provider, model, key) instead of a new `AsyncAnthropic` per message.
- **Application-controlled retries** (`llm/providers/anthropic.py`): SDK retries OFF (`max_retries=0`); bounded exponential backoff + jitter with retryable (429/5xx/timeout/connection) vs non-retryable (auth/validation) classification. Configurable via `ANTHROPIC_MAX_RETRIES`.
- **Safe temperature handling**: temperature is omitted for model families that reject sampling params (Opus 4.6–4.8, Sonnet 5/4.6, Fable/Mythos 5) so a configured temperature can't cause a 400.
- **Config-driven limits wired into the agent**: history message/char windowing (`_windowed_history`), configured `max_tokens`, and the `ANTHROPIC_TOOL_USE_ENABLED` toggle (falls back to plain completion when off).
- **`request_id` + `tool_rounds`** captured on `LLMResult` (normalized result for support/debugging).
- **`GET /health/ai`** (`api/health.py`): safe readiness (provider/enabled/configured/model/tool_use/live_ready) — **no key, no billed call**.
- **`scripts/test_anthropic.py`**: protected connectivity smoke test — validates config, sends one minimal real request, prints model/latency/tokens/request_id, redacts the key from any error, exits non-zero on failure. Verified live (`req_011CdNQ…`, exit 0).

**Tests:** +16 (`test_ai_config.py`, `test_anthropic_retry.py`, `test_health_ai.py`). **451 passed**, 0 failures. Suite still hermetic (mock).

**Consciously deferred (see "Architectural decision" below):** Claude-orchestrated booking via write tools (`save_*`), a dedicated `llm_usage_events` table + migration (currently persisted to `messages.metadata`), conversation-summary compaction, per-conversation locking / `workflow_version`, admin AI settings UI, multi-model routing, and moving the AI turn to a background worker. These are larger and/or would touch the working deterministic FSM; they were not built to honour "smallest safe version / do not overbuild."

### Architectural decision required — booking orchestration
The spec's write-tool list (`save_pickup_date`, `save_service_selection`, `confirm_order`, …) implies **Claude drives the booking** by requesting tools the backend validates/executes. The current, working design keeps **booking fully deterministic** (`services/booking_flow.py` FSM, no LLM) and uses Claude only on the **non-booking** path with **read-only** grounded tools. Both satisfy "the backend validates and the DB is authoritative", but they are different architectures. Recommendation: keep the deterministic FSM (lower regression risk; it already satisfies DoD items 13–16) and expand Claude's read-only NLU role — unless the owner wants Claude to orchestrate booking via write tools, which is a larger, separately-scoped change.
