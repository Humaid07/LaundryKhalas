# Build Report — WhatsApp Agent: Haiku 4.5 + No-Dash Replies + Mixed Prompt Caching

**Date:** 2026-07-31
**Author:** Engineering (Claude Code session)
**Area:** `apps/whatsapp-agent` (customer-facing WhatsApp runtime only)

## 1. Task objective
Ship three related changes as one end-to-end update to the existing WhatsApp
Operations Agent, without disturbing Evolution integration, FastAPI, Supabase,
the Anthropic tool loop, booking FSM, facility routing, pricing, human
intervention, or the dashboards:

1. Stop using dashes in customer-facing WhatsApp replies.
2. Move the main WhatsApp LLM from Claude Sonnet to Claude Haiku 4.5 (cost).
3. Enable Anthropic prompt caching with the best supported structure
   (1h stable prompt/tools + 5m conversation history).

## 2. What was built (summary)
- **Model centralisation → Haiku 4.5.** One setting (`ANTHROPIC_WHATSAPP_MODEL`)
  is now the single source of truth for the WhatsApp runtime model; it overrides
  the legacy `ANTHROPIC_MODEL` / `LLM_MODEL`. Effective id: **`claude-haiku-4-5`**.
- **Deterministic no-dash normaliser** (`services/reply_style.py`) that runs
  immediately before every outbound customer message, plus explicit no-dash
  writing-style rules added to both stable system prompts.
- **Mixed prompt cache** in `AnthropicProvider`: 1h ephemeral cache on the stable
  system prompt + tool definitions, 5m ephemeral cache on the reusable
  conversation-history prefix, with all dynamic backend state and the newest
  customer message placed AFTER the last breakpoint. Usage fields (incl. per-TTL
  cache-creation split) captured and logged.

## 3. Why
- Haiku 4.5 is ~1/3 the input and 1/5 the output price of Sonnet 5 on the highest-
  volume path (see §21), with adequate quality for grounded, tool-driven booking.
- Dashes (bullets, em/en dashes, `6 PM - 8 PM`, `1-2 days`) make replies read like
  machine-generated reports; natural prose reads like a human CSR.
- Prompt caching cuts the dominant cost driver (the large stable system prompt +
  tool schemas re-sent every turn) by ~90% on cache reads.

## 4. Files created
- `apps/whatsapp-agent/services/reply_style.py` — deterministic no-dash normaliser.
- `apps/whatsapp-agent/agents/whatsapp_agent/context_assembly.py` — cache-aware
  message assembler (places 1h/5m breakpoints; dynamic state after them).
- Tests: `tests/test_reply_style.py`, `tests/test_whatsapp_model_selection.py`,
  `tests/test_prompt_cache_structure.py`, `tests/test_llm_cost_report.py`,
  `tests/_fake_anthropic.py` (shared scripted client).

## 5. Files modified
- `settings.py` — new knobs: `anthropic_whatsapp_model`, `anthropic_whatsapp_temperature`,
  `anthropic_extended_thinking`, `anthropic_prompt_cache_enabled`,
  `anthropic_system_cache_ttl`, `anthropic_history_cache_ttl`. New resolvers
  `anthropic_model_effective` (whatsapp → anthropic → llm → default) and
  `anthropic_temperature_effective`. `ai_status` + `validate_ai_config` extended.
- `llm/service.py` — passes cache/temperature/thinking config into the provider;
  cache key widened so a settings change rebuilds the client.
- `llm/providers/base.py` — `LLMMessage.cache` hint; `LLMResult` cache-write split
  + `cache_hit` / `total_input_tokens`.
- `llm/providers/anthropic.py` — mixed 1h/5m cache placement, extended-cache beta
  header when 1h is in play, per-TTL usage capture, `refusal` stop-reason → raise,
  single sampling param, thinking never sent.
- `agents/whatsapp_agent/agent.py` and `agents/whatsapp_agent/booking_tools.py` —
  use the assembler; dynamic facts/state moved out of `system` into the final user
  turn; booking-turn log now records cache metrics. No-dash style rules added to
  `booking_system_prompt()` and `prompts.build_system_prompt()`.
- `api/evolution_webhooks.py` — normaliser wired into every outbound choke point
  (`_deliver`, `_send_plain`, and the general auto-reply path) with the
  `customer_reply_style_normalized` structured log (metadata only, no full reply).
- `services/metrics.py` — `build_llm_cost_report()` aggregate (cache hit/miss,
  tokens, cost per conversation/turn, error/intervention/normalisation rates).
- `.env` / `.env.example` — Haiku model + temperature + thinking + cache config.
- `tests/test_anthropic_tool_loop.py` — updated the cache-shape assertion to 1h.

## 6. API endpoints
No new HTTP endpoints. `ai_status` (health/diagnostics) now also reports the
effective model, extended-thinking flag, temperature, and cache config.

## 7. Database
No schema/migration changes. Per-turn usage (tokens, cache read/write, cost) is
persisted as message metadata exactly as before; the booking-turn log gained cache
fields. The database remains authoritative for all business state.

## 8. Agent behaviour
- Runtime model is Haiku 4.5. No hidden Sonnet fallback — the only fallback on any
  provider/loop failure is the deterministic MockProvider (safe, never invents),
  and a `stop_reason=refusal` now raises into that same safe path instead of being
  sent as a reply or treated as a completed booking.
- Replies must not use dash formatting (prompt rule + deterministic safety net).
- Dynamic per-turn/per-customer context (date, persona name, order state, prices,
  newest message) is delivered after the cache breakpoints, so the shared prefix is
  byte-identical across customers and personas.

## 9. Prompt cache structure
```
tools (1h ephemeral)                    ← stable, identical across customers/turns
system: stable prompt (1h ephemeral)    ← booking/style/safety rules, tool guidance
messages:
  history turns …                       ← 5m ephemeral breakpoint on the last one
  FINAL user turn                        ← dynamic backend state + newest message (uncached)
```
- 1h breakpoint: last tool + stable system block; beta header
  `extended-cache-ttl-2025-04-11` sent whenever a 1h breakpoint is present.
- 5m breakpoint: last conversation-history turn (refreshed on each reuse, so an
  active chat keeps hitting it well past five wall-clock minutes; a >5-minute gap
  lets it expire while the 1h system cache and DB state survive).
- No unsupported "7-minute" cache exists.
- Haiku's minimum cacheable prefix is 4096 tokens; the stable system prompt + tool
  schemas exceed this, so the 1h prefix caches. Below-threshold prompts silently
  won't cache (no error) — this is expected and logged as a miss.

## 10. What is mock-only / live
- Mock-first preserved: with no live key the MockProvider answers and none of the
  cache/model code path runs. All new tests are fully offline (scripted client).
- Live: the owner's `.env` already runs `LLM_PROVIDER=anthropic` with a real key for
  manual TEST-mode WhatsApp; this change switches that live model to Haiku 4.5 and
  turns on caching. No new external integration was enabled.

## 11. What is intentionally deferred
- Live end-to-end verification against the real Haiku API (cache-write/read usage
  on a real key), one full live booking, and one post-confirmation change — these
  require a live key + Evolution session and are a manual TEST-mode step (§ Deploy).
- A historical-replay evaluation *run* against live Haiku (the harness exists under
  `eval/`; running it consumes live tokens).
- An admin dashboard surface for `build_llm_cost_report` (backend aggregate is
  ready; no UI was added).

## 12. Tests run
- New: `test_reply_style.py`, `test_whatsapp_model_selection.py`,
  `test_prompt_cache_structure.py`, `test_llm_cost_report.py` — all pass.
- Updated: `test_anthropic_tool_loop.py` (1h cache shape) — passes.
- Regression: booking/item/agent/persona/webhook/delivery/auto-reply suites — pass.
- Full suite: see §17 (run at end of session).

## 13. Test results
- Focused suites: **30 new + updated pass**; booking/agent (46) + webhook/delivery/
  auto-reply (47) pass. Ruff clean on all changed + new files.
- Full-suite result recorded in the completion summary (baseline was ~1130 pass, 1
  pre-existing unrelated failure).

## 14. Known limitations
- The normaliser converts a bare tight numeric range only when it is `d-d`; all-
  digit sequences with 2+ hyphens (phone/ref) are preserved and NOT range-converted.
- Em/en dash separators become `. ` / `, ` deterministically; the exact human
  rewrite (e.g. "After the approved discount…") comes from the prompt, not the
  regex — the regex only guarantees the dash is gone and text stays readable.
- 1h TTL is treated as GA per the current SDK reference; the beta header is sent
  defensively. If an account lacks it, disable caching via
  `ANTHROPIC_PROMPT_CACHE_ENABLED=false` (safe rollback).

## 15. Security / privacy
- `customer_reply_style_normalized` logs metadata only (conversation id, dash count,
  rules applied, validation result) — never the full reply.
- No PII enters the stable cached prefix; persona name, phone, address, coordinates,
  order state all sit after the last breakpoint.
- No secrets committed; `.env` (with the live key) is untracked and only its model/
  cache lines were edited.

## 16. Cost / LLM usage
- Per-turn usage now records `input_tokens`, `output_tokens`,
  `cache_read_input_tokens`, `cache_creation_input_tokens`, and the per-TTL split
  when present; cost is estimated from ACTUAL token buckets (`llm/costs.py`), not
  prompt length. Cache reads bill ~0.1×, 5m writes ~1.25×, 1h writes ~2×.

## 17. Cost comparison (estimate)
| | Sonnet 5 | Haiku 4.5 |
|---|---|---|
| Input $/1M | 3.00 (2.00 intro) | 1.00 |
| Output $/1M | 15.00 (10.00 intro) | 5.00 |
Combined with prompt caching (large stable prefix served at ~0.1× on cache reads),
the expected per-conversation cost drop is substantial (model ~3× cheaper input /
~3× cheaper output, plus caching removing most repeated input). Exact figures to be
confirmed from live `usage` via `build_llm_cost_report` after TEST-mode traffic.

## 18. Commands to run
```
cd apps/whatsapp-agent
./.venv/Scripts/python.exe -m pytest tests/test_reply_style.py \
  tests/test_whatsapp_model_selection.py tests/test_prompt_cache_structure.py \
  tests/test_llm_cost_report.py -q
./.venv/Scripts/python.exe -m ruff check services/reply_style.py \
  agents/whatsapp_agent/context_assembly.py llm/providers/anthropic.py
```

## 19. How to verify manually (TEST mode)
1. Confirm effective model: `ai_status.model == claude-haiku-4-5`.
2. Send a WhatsApp message that would tempt dashes ("what are your hours / how long
   does dry clean take") and confirm the reply has no `-`/`–`/`—` prose and ranges
   read "6 PM to 8 PM" / "1 to 2 days".
3. Second message in the same chat: check logs for `cache_read_tokens > 0`.
4. Run one full booking + one post-confirmation change; confirm order confirmed once.
5. Trigger a refund/complaint; confirm human intervention created and AI paused.

## 20. Rollback
- Model: set `ANTHROPIC_WHATSAPP_MODEL=claude-sonnet-5` (no code change).
- Caching: `ANTHROPIC_PROMPT_CACHE_ENABLED=false`.
- Normaliser is additive and safe; to disable, revert the three `_normalize_*` call
  sites. Style prompt rules are inert text.

## 21. Next recommended step
Run one TEST-mode live conversation to capture real `usage` values, feed them
through `build_llm_cost_report`, and record the measured cost delta and cache hit
rate in the weekly report; then decide on flipping the live WhatsApp mode.
