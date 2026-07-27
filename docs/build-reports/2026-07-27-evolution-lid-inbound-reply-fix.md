# Build Report — Evolution LID inbound fix (agent "no reply") + live bring-up

- **Date:** 2026-07-27
- **Task objective:** Bring the whole stack up live for manual WhatsApp testing, and fix the persistent bug where the agent never replies after an approved test number messages it.

## What was built / changed

Root-caused the recurring "agent gives no reply" to **two stacked blockers** and fixed both.

### 1. WhatsApp LID addressing (real, code-level root cause)
Newer WhatsApp/Baileys uses **LID addressing**: `key.remoteJid` becomes an opaque
LID (e.g. `58239773319181@lid`) that is **not** a phone number. The real
phone-number JID (`971543216640@s.whatsapp.net`) is carried alongside in
`key.remoteJidAlt` (1:1) / `key.participantAlt` (group).

`parse_evolution_webhook` read the `remoteJid` digits as the phone number →
`normalize_e164` produced a garbage number → it **never matched
`EVOLUTION_ALLOWED_TEST_NUMBERS`** → every inbound was logged
`evolution_inbound_skipped … reason=sender_not_allowed`. A previous
"fix" (`POST /instance/restart`) only reverted contacts to PN addressing
temporarily, which is why the failure kept coming back.

**Fix:** new `_resolve_sender_phone(key)` in
`apps/whatsapp-agent/channels/evolution_whatsapp.py` — prefers `remoteJidAlt`
when `remoteJid` ends with `@lid`, strips a `:device` suffix, and falls back to
the LID digits only when no alt is present (so the message is still stored,
never silently dropped). Groups stay ignored (their `remoteJid` is still
`@g.us`).

### 2. Stuck `human_takeover` conversation (operational blocker)
Even after the number resolved, the `+971543216640` conversation was
`status='human_takeover'`, so the webhook held it
(`no_auto_reply_reason=human_takeover`) and the AI stayed silent **by design**.
Released it back to `bot`. (Behaviour is correct — escalations/takeovers silence
the AI for that number until released — but it compounded the LID bug into a
total "never replies" symptom.)

## Files created / modified
- **Modified:** `apps/whatsapp-agent/channels/evolution_whatsapp.py` (added `_resolve_sender_phone`, used it in the parser).
- **Modified:** `apps/whatsapp-agent/tests/test_evolution_channel.py` (+4 tests: LID→real number, LID w/o alt fallback, `:device` suffix strip, LID group still ignored).
- **Created:** `apps/admin/.env.local` (points dashboard at :8100, enables live inbox).
- **Data change (test DB):** released the `+971543216640` conversation from `human_takeover` → `bot`.

## API endpoints / DB models / UI
- No API, schema, or UI-component changes. The change is inside inbound webhook parsing only.

## What is mock / live / deferred
- **Live (by owner's earlier approval):** Anthropic Claude (`claude-sonnet-5`), Evolution WhatsApp, Supabase test DB.
- **Mock/off:** Stripe (no live payments exist), Meta Cloud API.
- **Deferred:** nothing new deferred.

## Tests run + results
- `pytest tests/test_evolution_channel.py` → **14 passed**.
- Full suite `pytest -q` → **493 passed** (was 489; +4 new), 1 unrelated deprecation warning, in ~193s. Runs against SQLite (no live calls).

## Manual verification
- Injected a synthetic Evolution **LID** webhook from `971543216640@…lid` (real number in `remoteJidAlt`):
  - Before releasing takeover: `processed:1` but `evolution_inbound_held reason=human_takeover` (number resolved correctly — allow-list matched).
  - After releasing takeover: `anthropic_turn_started` → `anthropic_turn_delivered provider=anthropic tokens_in=1602 tokens_out=201` — a real Claude reply was generated and sent via Evolution.

## Bugs / limitations / notes
- Customers are stored with `phone_e164` **without** the leading `+` (e.g. `971543216640`); the allow-list comparison normalizes both sides, so this is fine.
- The connected Evolution line (+91 93725 22055 "Humaid") is a busy personal WhatsApp; the webhook fires for all its chats and non-allow-listed senders are correctly skipped.
- **Security:** the live Anthropic key is in `apps/whatsapp-agent/.env` (gitignored). It was pasted in chat previously — recommend rotating.

## How to run (bring the stack up)
- **Backend (:8100 — must match the Evolution webhook):**
  `cd apps/whatsapp-agent && ./.venv/Scripts/python.exe -m uvicorn main:app --host 0.0.0.0 --port 8100`
- **Dashboard (:3005):** `cd apps/admin && ./node_modules/.bin/next dev -p 3005`
- **Evolution API:** already dockerized on :8080 (instance `whatsapp-agent`, connected).
- Ignore the stale legacy docker containers `laundrykhalas_admin` (:3000) and `laundrykhalas_api` (:8000).

## Next recommended step
- Owner to run the real manual test: message **+91 93725 22055** from **+971 54 321 6640** or **+971 50 248 5658**.
- If approved, commit the fix to `main` (currently uncommitted).
