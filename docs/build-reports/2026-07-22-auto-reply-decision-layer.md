# Build Report — Auto-Reply Decision Layer for Evolution WhatsApp

**Date:** 2026-07-22

## 1. Task objective
Stop the live Evolution WhatsApp agent (with `EVOLUTION_AUTO_REPLY=true`) from
auto-replying — and re-sending the welcome message — to *every* inbound message.
Auto-reply only for genuinely laundry/LaundryKhalas-related messages, welcome at
most once per conversation, stay silent on unrelated chat, and never
auto-resolve risky/escalation topics.

## 2. What was built
A deterministic **auto-reply decision layer** (`should_auto_reply`) that runs in
the Evolution inbound webhook *before* any live send, plus the wiring that fixes
the real root cause of the repeated welcome.

## 3. Why
`api/evolution_webhooks.py` called `handle_message(..., history=[])` — empty
history — so every inbound looked like a fresh greeting and the mock agent
returned the welcome each time. It also auto-sent for every non-escalation
message regardless of topic.

## 4. Files created
- `apps/whatsapp-agent/services/auto_reply.py` — `should_auto_reply(message_text, conversation_context) -> AutoReplyDecision(send_reply, reason, intent, domain, allow_welcome)`. Domains: `laundry_related | out_of_domain | greeting_only | escalation`. Reuses `domain_guard.classify()` + `detect_escalation()` (no duplicated keyword lists).
- `apps/whatsapp-agent/tests/test_auto_reply.py` — 10 unit tests over the required example cases.

## 5. Files modified
- `apps/whatsapp-agent/api/evolution_webhooks.py` — loads real prior history, computes `welcome_sent` from prior agent messages, gates the live send on `should_auto_reply`, drafts escalation suggested-replies with real history, marks non-replied inbound `no_auto_reply` / `human_needed`.
- `apps/whatsapp-agent/db/repositories/messages_repo.py` — added `set_status(message_id, status)`.

## 6. API endpoints
No new routes. Behavior change inside `POST /webhooks/evolution` only.

## 7. DB tables/models
None changed. Welcome-once is inferred from existing `messages` rows (prior
`sender_type='agent'`) — no migration. Inbound message `status` now also takes
`no_auto_reply` / `human_needed` values (free-text column, no schema change).

## 8. Agent behavior
- Escalation (refund/complaint/damage/missing/payment/legal/angry) → flag +
  `human_needed`, **no autonomous reply** (suggested reply stored for operator).
- Laundry-related → auto-reply, continue flow (welcome only if not welcomed yet).
- First bare greeting ("hi"/"hello") → welcome **once**; repeats → silent.
- Out-of-domain / ack / emoji / uncertain → stored, marked `no_auto_reply`, no send.

## 9. Mock-only vs live
Decision layer is deterministic (no LLM). Reply text still comes from the mock
LLM provider. Live sends go out only when `EVOLUTION_AUTO_REPLY=true` AND the
decision approves.

## 10. Deferred
- Not auto-sending a "safe acknowledgement" on escalation (kept fully silent —
  safest, matches MVP approval rule). Operator sends the suggested reply.
- Live LLM for higher-quality replies (still `llm_provider=mock`).
- Persisted `welcome_sent` column (currently inferred from messages).

## 11. Tests run
`pytest tests/test_auto_reply.py` → 10 passed. Full suite `pytest` → **184 passed**.
Module imports verified.

## 12. Known limitations
- Reply *quality* still limited by the mock LLM (shallow slot-filling).
- Keyword-based domain detection can misclassify novel phrasings (uncertain →
  silent by design, so it errs toward not spamming).

## 13. Security/privacy
No new PII surfaces. Existing masking unchanged. No secrets touched.

## 14. How to verify manually
With backend on `:8101`, `WHATSAPP_MODE=evolution`, `EVOLUTION_AUTO_REPLY=true`:
- Send "test" / "okay" / random emoji → no WhatsApp reply; inbox message marked `no_auto_reply`.
- Send "hi" twice → welcome only the first time.
- Send "Hi, I need laundry pickup today" → normal reply, flow continues.
- Send "I want a refund. My clothes came back dirty." → no auto-reply; `human_needed`/`urgent`/`refund_request` flag created.

## 15. Next recommended step
Re-run the supervised live test (normal + escalation) to confirm behavior on the
wire, then consider enabling a real LLM provider for reply quality.
