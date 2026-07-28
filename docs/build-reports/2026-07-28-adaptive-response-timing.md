# Build Report — Adaptive WhatsApp response timing (per-conversation debounce)

**Date:** 2026-07-28

## Objective
Make the agent feel responsive without replying prematurely: process clearly
complete messages fast, still combine fragmented ones, and handle structured
actions with minimal delay — replacing the single fixed 5s/15s aggregation window.

## Profiling / audit (before)
End-to-end path: Evolution webhook → validate + dedup (wa_message_id) → store
message → buffer into a durable `conversation_turns` turn → **debounce timer** →
combine → ONE Anthropic turn → tools → Evolution send → store outbound.

- **Dominant customer-perceived delay = the fixed inactivity debounce.** Every
  message — including a complete "How much is shirt cleaning?" — waited the same
  `whatsapp_message_debounce_seconds=5.0` before Anthropic was even called; the
  hard cap was `15.0s`.
- **Already optimised (left unchanged):** ONE Anthropic call per *logical turn*
  (not per fragment); history limits (`ANTHROPIC_HISTORY_MESSAGE_LIMIT=20`,
  `ANTHROPIC_HISTORY_CHARACTER_LIMIT=20000`); bounded `ANTHROPIC_MAX_TOOL_ROUNDS=5`;
  pooled asyncpg + reused Anthropic/Evolution clients; the webhook returns `200`
  after buffering (processing runs in an asyncio task, not in the request);
  restart recovery; per-conversation lock + optimistic DB claim (one reply/turn);
  duplicate-webhook dedup; bare interactive selections already flush immediately.
- **Model** is already `claude-sonnet-5` (not Opus). No model change needed.

Conclusion: the fix is **adaptive debounce**, not a prompt/model/queue change.

## What was built
1. **`services/message_completeness.py`** — a fast, LOCAL, deterministic classifier
   (NO LLM call) returning `STRUCTURED_ACTION | URGENT_OPERATIONAL_ACTION |
   COMPLETE | LIKELY_COMPLETE | LIKELY_FRAGMENT`, plus a label→debounce-tier map.
2. **Centralised config (`settings.py`)** — `WHATSAPP_DEBOUNCE_SHORT_MS=500`,
   `WHATSAPP_DEBOUNCE_STANDARD_MS=1000`, `WHATSAPP_DEBOUNCE_FRAGMENT_MS=3000`,
   `WHATSAPP_MAX_AGGREGATION_MS=8000`, plus `WHATSAPP_TYPING_INDICATOR_ENABLED`,
   `WHATSAPP_SLOW_RESPONSE_THRESHOLD_MS`, `WHATSAPP_RESPONSE_TIMEOUT_MS` + second
   helper properties. Durations live in ONE place (never hardcoded per file).
3. **Adaptive per-fragment debounce (`services/turn_service.py`)** —
   `add_fragment` now accepts the classifier-chosen `debounce_seconds`; the turn's
   deadline is capped at `first_message_at + max` so slow fragments can't postpone
   processing past the hard window.
4. **Max-window preservation (`db/repositories/turns_repo.py`)** — an APPEND caps
   `aggregation_deadline_at` at `first_message_at + max_seconds`.
5. **Webhook wiring (`api/evolution_webhooks.py`)** — classify each inbound once,
   log `message_completeness_classified` + `adaptive_debounce_selected`, pass the
   adaptive wait into `add_fragment`. The existing immediate-flush for bare
   selections / "that's all" is kept.

## Behaviour (verified live)
| Message | Class | Debounce |
|---|---|---|
| "How much is shirt cleaning?" | COMPLETE | **1000ms** (was 5000) |
| "Hi" / "tomorrow" / "from Marina" | LIKELY_FRAGMENT | 3000ms (combine) |
| list/slot/location selection | STRUCTURED_ACTION | 500ms |
| "Yes, confirm" / "Cancel order" | URGENT_OPERATIONAL_ACTION | 500ms |
| a plain sentence | LIKELY_COMPLETE | 1000ms |

Max aggregation window: **8s** (was 15s). Per-conversation isolation, one-reply-
per-turn, dedup and restart-recovery are all unchanged.

## Configuration added
`WHATSAPP_DEBOUNCE_SHORT_MS`, `WHATSAPP_DEBOUNCE_STANDARD_MS`,
`WHATSAPP_DEBOUNCE_FRAGMENT_MS`, `WHATSAPP_MAX_AGGREGATION_MS`,
`WHATSAPP_TYPING_INDICATOR_ENABLED`, `WHATSAPP_SLOW_RESPONSE_THRESHOLD_MS`,
`WHATSAPP_RESPONSE_TIMEOUT_MS` (all with defaults; legacy
`whatsapp_message_debounce_seconds/max` retained as fallback).

## Logging added
`message_completeness_classified`, `adaptive_debounce_selected` (conversation id +
classification + debounce_ms; no PII/phones/keys).

## Files changed
- new `services/message_completeness.py`
- `settings.py`, `services/turn_service.py`, `db/repositories/turns_repo.py`,
  `api/evolution_webhooks.py`
- new `tests/test_message_completeness.py`; `tests/test_turn_service.py`

## Tests + results
- `test_message_completeness.py` — **29 passed**: every spec example (complete,
  fragment, structured, confirm/cancel, answers-requested-field, likely-complete)
  + debounce-tier mapping (complete < fragment; structured shortest).
- `test_turn_service.py` — **11 passed** incl. 3 new: adaptive short deadline for a
  complete message, fragment waits longer than complete, and the max window
  preserved across slow fragments (mocked clock — no real timers).
- `test_message_aggregation.py` — 13 passed. ruff clean.
- **Live**: replayed "How much is shirt cleaning?" → COMPLETE/1000ms and "Hi" →
  LIKELY_FRAGMENT/3000ms on two conversations; logs confirm independent adaptive selection.

## Manual verification
Message the agent a complete question — it replies quickly (~1s wait + model). Send
three fragments ("Hi" / "carpet cleaning" / "tomorrow") within a couple of seconds —
they combine into ONE reply shortly after the last fragment. Tap a list option / send
"Yes, confirm" — processed with the shortest wait. Backend logs show
`adaptive_debounce_selected` with the per-message `debounce_ms`.

## Honestly deferred (NOT done this pass — with reasons)
- **Typing/presence indicator send** — config flag added (`WHATSAPP_TYPING_INDICATOR_ENABLED`,
  default off) but the Evolution `setPresence` call is **not** wired (composing-presence
  rendering is inconsistent across Baileys/WhatsApp-Web builds — needs a reliability trial).
- **Latency-percentile admin view** (p50/p75/p95, % under 3/5/8s, by message-type/model/
  tool-count) — the structured events are the foundation, but the metrics store + admin
  dashboard (separate Next.js app) are a separate build.
- **Full per-stage timestamp instrumentation** + `slow_response_detected` /
  `response_timeout_detected` emission — threshold config added; wiring into the processor deferred.
- **Turn-level timeout wrapper + parallel independent read-only tools** — Anthropic already
  has bounded retry/timeout; a unified turn timeout and concurrent tool fetch are follow-ups.
- No CRM/queue-broker introduced; the existing in-process debounce + durable DB claim +
  restart recovery remain the architecture.

## Remaining bottlenecks
After the debounce fix, the dominant remaining latency is the **Anthropic model call**
itself (seconds), which is expected and bounded by history/tool-round limits. A complete
FAQ now targets ~1s wait + model time; fragments reply ~3s after the last fragment.
