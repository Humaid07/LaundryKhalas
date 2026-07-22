# Build Report — Evolution Auto-Reply Sender Allow-List (Safety Fix)

**Date:** 2026-07-22
**Author:** Engineering (Claude)
**Related:** [[2026-07-22-auto-reply-decision-layer]] · [[2026-07-21-supabase-dev-test-setup]] · [[whatsapp-provider-modes]]

## 1. Task Objective
Stop the Evolution WhatsApp auto-reply from replying to **every** inbound number.
During live testing the agent must auto-reply **only** to an approved test/customer
number, and even then only for safe, laundry-related messages.

## 2. What Was Built
A **sender allow-list gate** that runs before the agent is ever called:

1. Normalize the inbound sender to E.164 (handles all Evolution/Baileys shapes).
2. If the sender is **not** on `EVOLUTION_ALLOWED_TEST_NUMBERS`: do not store, do
   not call the agent, do not send anything — log the skip (masked) and return
   `200 OK` so Evolution does not retry.
3. If the sender **is** allowed: store the message, then run the existing
   domain/escalation decision layer (`should_auto_reply`) — reply only when the
   message is laundry-related (welcome once), hold escalations for a human.

## 3. Why
The webhook auto-sent the happy-path draft to any inbound sender whenever
`EVOLUTION_AUTO_REPLY=true`. A live WhatsApp number replying to strangers is a
safety, privacy, and brand risk. `EVOLUTION_AUTO_REPLY=true` now means
"auto-reply **only** for allowed test numbers and **only** for safe,
laundry-related messages."

## 4. Files Created
- `apps/whatsapp-agent/tests/test_auto_reply_gate.py` — 11 tests (the 5 required
  scenarios + normalization + settings parsing + allowed-sender escalation).
- `docs/build-reports/2026-07-22-evolution-sender-allowlist.md` — this report.

## 5. Files Modified
- `apps/whatsapp-agent/settings.py` — new `evolution_allowed_test_numbers` field
  + `allowed_auto_reply_numbers` (normalized `frozenset[str]`) property.
- `apps/whatsapp-agent/services/privacy.py` — new `normalize_e164()` (single
  source of truth for sender normalization, reused by settings + webhook).
- `apps/whatsapp-agent/services/auto_reply.py` — new `evaluate_inbound()` +
  `InboundDecision` (sender gate + message decision, the pure/testable combo) and
  `SENDER_NOT_ALLOWED` constant.
- `apps/whatsapp-agent/db/repositories/messages_repo.py` — new `has_agent_reply()`
  (welcome-once check).
- `apps/whatsapp-agent/api/evolution_webhooks.py` — sender gate at the top of the
  per-message loop; masked, structured logs (`allowed_sender`,
  `auto_reply_decision`, `no_auto_reply_reason`); `skipped` count in the response.
- `apps/whatsapp-agent/.env.example` — documented `EVOLUTION_ALLOWED_TEST_NUMBERS=`.
- `apps/whatsapp-agent/.env` (**not committed**) — corrected the allow-list to the
  approved test number `+9715…58`.

## 6. API Endpoints
`POST /webhooks/evolution` — unchanged path; response now includes `skipped`
(count of non-allowed senders dropped). Always returns `200 OK`.

## 7. Database
No schema changes. New read helper only (`messages.has_agent_reply`).

## 8. Behaviour: Auto-Reply Decision Order
1. Drop `fromMe` / group / status / non-text (parser).
2. Normalize sender → E.164.
3. Sender **not** allowed → no store, no agent, no send, reason `sender_not_allowed`.
4. Sender allowed → store, then decision layer:
   - escalation (refund/complaint/damage/…) → **Human Needed** + flag, never auto-sent;
   - laundry-related / first bare greeting → auto-reply (if `EVOLUTION_AUTO_REPLY=true` and live-ready);
   - unrelated / repeat greeting / ack → held (`no_auto_reply`).

## 9. What Is Mock / Live
- Live: Evolution send/receive (`WHATSAPP_MODE=evolution`), Supabase inbox.
- Held/never-live: escalations, non-allowed senders, non-laundry messages.
- Mock: LLM (`LLM_PROVIDER=mock`), Stripe (off).

## 10. Tests Run & Results
`python -m pytest` → **195 passed** (incl. 11 new gate tests). The 5 required
scenarios all pass:
1. allowed + laundry → reply ✅
2. allowed + "hello bro" → no reply ✅
3. stranger + laundry → no reply, `sender_not_allowed` ✅
4. stranger + refund → no reply, **no customer-facing draft** ✅
5. allowed + repeated "hi" → welcome sent once, not repeated ✅

## 11. Security / Privacy
- Full numbers never logged — only `mask_phone()` output. API keys / DATABASE_URL /
  Supabase password / Evolution key never logged or printed.
- Empty allow-list = auto-reply to **no one** (fail safe).
- `.env` not committed.

## 12. Known Limitations / Notes
- `EVOLUTION_ALLOWED_TEST_NUMBERS` was found set to a **different** number
  (`+971543216647`); corrected to the approved `+971502485658` per instruction.
- `.env` has a duplicate `WHATSAPP_MODE=evolution` line (both identical, benign) —
  left untouched to avoid clobbering a concurrent edit; worth de-duping later.
- Running server picks up `.env` changes only on reload (`--reload` watches `.py`);
  a worker reload was forced after the `.env` edit.

## 13. How to Verify Manually
1. Backend live on `http://localhost:8101` (`/health`, `/health/db`, `/api/conversations`,
   `/api/orders/active`, `/api/flags` all 200).
2. From **+971502485658** → "Hi, I need laundry pickup today" → expect
   `POST /webhooks/evolution 200`, `evolution_auto_reply_sent`, live reply.
3. From any other number → expect `evolution_inbound_skipped` /
   `no_auto_reply_reason=sender_not_allowed`, **no** reply.
4. From +971502485658 → "I want a refund. My clothes came back dirty." → expect
   Human Needed + `refund_request`/urgent flag, **no** auto-reply.

## 14. Next Recommended Step
Run the live end-to-end test (steps above) and confirm inbound storage + the
refund escalation flag in the Supabase-backed dashboard inbox.
