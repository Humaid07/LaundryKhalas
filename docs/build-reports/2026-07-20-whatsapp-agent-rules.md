# Build Report — WhatsApp Agent Business & Safety Rules Config Layer

**Date:** 2026-07-20
**Module:** Standalone WhatsApp Agent (`apps/whatsapp-agent`, `:8100`)
**Status:** ✅ Built, tested (117 passed), live mock server restarted & verified. Mock-only.

---

## 1. Task objective

Introduce a **rules/config layer** for the standalone LaundryKhalaas WhatsApp
agent so its business and safety rules (domain scope, welcome/refusal wording,
service menu, escalation/handoff, mock-mode honesty, privacy, tone, logging)
are read from config files instead of being hardcoded in prompts and code —
**without rebuilding the agent, building the classifier, touching the admin
dashboard, or connecting any live API.**

## 2. What was built

- **Six config files** under `apps/whatsapp-agent/config/`.
- A single **leaf loader** `rules.py` (cached) that every rule surface reads
  from — no module imports a config file path directly anymore.
- **Two small services:** `services/escalation.py` (deterministic handoff
  detection) and `services/privacy.py` (PII masking for the audit log).
- The existing agent modules were **rewired to read from config** (prompts,
  actions, tools, mock provider, domain guard) — behaviour preserved, source
  moved to config. A new **escalation short-circuit** was added to `agent.py`.
- Logging enriched (RULE 11) and PII-masked (RULE 8).
- New test file `tests/test_agent_rules.py` covering the spec's 10 cases.

## 3. Files created

- `config/whatsapp_agent_rules.json` — master domain/welcome/booking/privacy rules
- `config/laundry_services.json` — service catalog + pricing (single source of truth)
- `config/quick_actions.json` — main-menu buttons + id→intent map
- `config/escalation_rules.json` — handoff categories + message
- `config/mock_mode_rules.json` — demo-mode wording
- `config/agent_tone_rules.json` — tone/system-prompt guidelines
- `rules.py` — central cached loader
- `services/escalation.py` — `detect_escalation()`
- `services/privacy.py` — `mask_pii()`
- `tests/test_agent_rules.py` — 22 rule-layer test cases
- Docs: `architecture/whatsapp-agent-rules.md`, `checklists/whatsapp-agent-rule-test-script.md`, this report

## 4. Files modified

- `agents/whatsapp_agent/agent.py` — escalation/handoff short-circuit + `handoff` field
- `agents/whatsapp_agent/actions.py` — buttons/intents built from config
- `agents/whatsapp_agent/prompts.py` — system prompt composed from config
- `agents/whatsapp_agent/tools.py` — service keywords/labels/pricing from config
- `llm/providers/mock.py` — welcome text, demo tags, service labels from config; booking honesty ack
- `services/domain_guard.py` — refusal message from config
- `api/chat.py`, `api/webhooks.py` — enriched + PII-masked logging
- `config/laundrykhalaas_knowledge.json` — services/pricing **removed** (moved to `laundry_services.json`); keeps area gazetteer + notes

## 5. API / DB / agent behaviour changes

- **API:** no endpoint signatures changed. `/api/test-chat/message` responses
  unchanged in shape.
- **DB:** no schema change. `agent_logs.output_json` now also carries
  `handoff`, `llm_mode`, `whatsapp_mode`, `domain`; `action` is `"handoff"` for
  escalations. Message text in logs is PII-masked.
- **Agent:** new deterministic **escalation/handoff** path (complaint, refund,
  damaged/missing item, late delivery, payment issue, B2B, legal/safety,
  anger) → short-circuits with the configured handoff message, no LLM call, no
  autonomous resolution. Completed mock bookings now explicitly say "Demo mode".

## 6. What is mock-only / live / deferred

- **Mock-only:** all of it. `LLM_PROVIDER=mock`, `WHATSAPP_MODE=mock`. No live
  WhatsApp/LLM/Stripe/API calls; no secrets.
- **Live:** nothing new went live.
- **Deferred:** classifier-based intent/sentiment (still keyword-based here),
  admin-editable rules UI, config hot-reload, street-address masking.

## 7. Tests run & results

```
cd apps/whatsapp-agent && .venv/Scripts/python.exe -m pytest -q
→ 117 passed, 1 error
```

- **117 passed** (was 95; +22 new rule tests).
- The **1 error** is a pre-existing Windows-only teardown issue: the session
  fixture cannot `unlink` the temp SQLite test DB because a connection handle
  is still held. It is **not** a test failure and predates this task.
- **In-process smoke** (`handle_message`) confirmed: welcome+menu, refund→
  handoff (`handoff=True`, `provider=none`, Call Support), curtains→no invented
  price, out-of-domain→configured refusal, system prompt builds.
- **Live server smoke** (`:8100` restarted): refund message returns the handoff
  JSON with the `call_support` action and `mode:"mock"`.

## 8. Bugs / issues found

- None introduced. Found and resolved a **dual-source-of-truth** risk: service
  pricing existed in both `laundrykhalaas_knowledge.json` and would now be in
  `laundry_services.json` — removed it from the knowledge file so pricing has
  exactly one home.

## 9. Security / privacy notes

- `mask_pii()` masks phone/email in the audit log and any outward view; raw
  transcript kept only in the conversation record for context (RULE 8 / §7).
- Domain guard still refuses prompt-injection and out-of-domain **before** any
  LLM call. No secrets added; `.env` untouched.

## 10. Cost / LLM usage

- Zero. Mock provider only; no tokens billed.

## 11. How to verify manually

See [[whatsapp-agent-rule-test-script]]. Quick version:

```bash
cd apps/whatsapp-agent
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m uvicorn main:app --port 8100
# POST {"message":"I want a refund for my order"} → handoff + Call Support
```

## 12. Next recommended step

When the classifier agent (deferred, §9) is built, have it produce the
escalation category and feed it into this same handoff path, replacing the
keyword `detect_escalation()` while keeping `escalation_rules.json` as the
config surface.
