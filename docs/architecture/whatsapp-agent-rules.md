# WhatsApp Agent — Business & Safety Rules Config Layer

**App:** `apps/whatsapp-agent` (standalone, `:8100`)
**Status:** ✅ Built, mock-only. 117 backend tests pass.
**Related:** [[standalone-whatsapp-agent]] · [[domain-guard]] · [[privacy-firewall]] · [[whatsapp-agent-architecture]]

---

## 1. Why this exists

The agent's business and safety rules (what it can talk about, the exact
welcome/refusal wording, the service menu, when to hand off to a human, how it
talks about demo mode, its tone) used to be spread across hardcoded strings in
`prompts.py`, `mock.py`, `actions.py`, `tools.py` and `domain_guard.py`.

They now live in a **config layer** — six JSON files under
`apps/whatsapp-agent/config/`, loaded once (cached) through a single leaf
module `rules.py`. Non-engineers can change the agent's behaviour by editing
config, with no code change (restart to reload).

This maps directly to CLAUDE.md §5 ("config is the source of truth"), §7
(privacy firewall), §8 (WhatsApp agent scope) and §20 (honesty).

## 2. The config files

| File | Drives | Read by |
|---|---|---|
| `whatsapp_agent_rules.json` | Master rules: domain scope + **refusal message**, **welcome message**, booking-flow steps, no-invented-data list, privacy fields | `domain_guard.py`, `prompts.py`, `mock.py` |
| `laundry_services.json` | **Service catalog**: key, label, keywords, per-service pricing (single source of truth) | `actions.py`, `tools.py`, `mock.py`, `prompts.py` |
| `quick_actions.json` | Main-menu buttons + `id → intent` map + service-button intent | `actions.py` |
| `escalation_rules.json` | **Handoff** trigger categories + keywords + handoff message + attached actions | `services/escalation.py`, `agent.py` |
| `mock_mode_rules.json` | Demo-mode wording (order/support tags, booking ack, tracking-unavailable) | `mock.py` |
| `agent_tone_rules.json` | Tone/style guidelines injected into the system prompt | `prompts.py` |

`laundrykhalas_knowledge.json` remains for the **area gazetteer** and market/
pickup notes only — the service catalog and pricing were **moved out of it** to
`laundry_services.json` so there is exactly one source of truth for services.

## 3. How the agent reads rules

```
config/*.json
     │  (json, cached with lru_cache)
     ▼
  rules.py        ← single leaf loader: agent_rules(), services_config(),
     │              quick_actions_config(), escalation_rules(),
     │              mock_mode_rules(), tone_rules() + helpers
     ├──────────────► domain_guard.py     REFUSAL_MESSAGE
     ├──────────────► prompts.py          system prompt (domain + tone + services)
     ├──────────────► actions.py          MAIN_MENU_ACTIONS / SERVICE_ACTIONS / id→intent
     ├──────────────► tools.py            service keywords, label→key, lookup_price
     ├──────────────► mock.py             welcome text, demo tags, service labels
     └──────────────► services/escalation.py  detect_escalation()
```

`rules.py` imports nothing from the agent, so any module can import it with no
cycle. Editing a config file requires a **service restart** to reload (the
loader is cached for per-message speed).

## 4. Rule-by-rule behaviour

- **RULE 1 — Domain scope.** `domain_guard.classify()` (layer 1, keyword) runs
  before any LLM call; out-of-domain returns the configured `refusal_message`
  with `provider="none"` (no LLM call). The system prompt (layer 2) repeats the
  restriction from config.
- **RULE 2 — Welcome.** Greetings return `welcome.message` with the six
  main-menu quick actions **attached to that message** (not a footer bar).
- **RULE 3 — Service options.** Book Pickup asks "which service?" and attaches
  buttons built **only** from `laundry_services.json`.
- **RULE 4 — Booking flow.** Step-by-step slot filling (service → items → area →
  time → review → confirm). In mock mode the completed booking appends
  `booking_ack` ("Demo mode — I've created a mock booking request…"). Never
  claims a real order.
- **RULE 5 — Quick actions.** Track/Change/Add/Cancel/Support each behave per
  `quick_actions.json` behaviour notes; Cancel never cancels, Change never
  auto-confirms.
- **RULE 6 — Escalation.** `services/escalation.py:detect_escalation()` matches
  `escalation_rules.json`. On a match the agent **short-circuits** with the
  handoff message (no LLM call, no autonomous resolution) and attaches the
  configured actions (Call Support). Cancellation/reschedule/tracking are
  handled by their own safe flows and are intentionally **not** re-escalated.
- **RULE 7 — No invented data.** `tools.lookup_price` returns `None` for any
  service with `pricing: null`; the agent then says the team will confirm.
- **RULE 8 — Privacy.** `services/privacy.py:mask_pii()` masks phone numbers and
  emails **before they enter the audit log** (`agent_logs`). The raw
  conversation transcript (`messages`) is kept for multi-turn context.
- **RULE 9 — Mock-mode honesty.** All demo wording comes from
  `mock_mode_rules.json`; when `WHATSAPP_MODE=live` the empty `live` tags make
  the demo wording disappear.
- **RULE 10 — Tone.** `agent_tone_rules.json` guidelines are injected into the
  system prompt.
- **RULE 11 — Logging.** Every turn writes an `agent_logs` row: user message
  (PII-masked), intent, action_id, domain, actions, `handoff`, `llm_mode`,
  `whatsapp_mode`, provider/model, success/error, timestamp.

## 5. Mock vs live

Everything here runs in **mock mode** (`LLM_PROVIDER=mock`,
`WHATSAPP_MODE=mock`). The rule layer is provider-agnostic: the same config
drives the mock responder today and a real Anthropic/OpenAI model later (the
tone + domain + no-invent rules are already in the system prompt). Going live
does not change the rules — only which provider generates the free text.

## 6. Known gaps / deferred

- Escalation detection is **keyword-based and deterministic**, not a classifier
  (the classifier agent is a separate, deferred module — CLAUDE.md §9). Angry-
  sentiment detection is limited to strong keywords.
- `mask_pii` masks phone/email only (not free-text street addresses); area/city
  is already preferred by design.
- Config changes need a **restart** (no hot-reload).
- Rules are not yet surfaced/editable from the admin dashboard (deferred).
