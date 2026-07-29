# Build Report — WhatsApp Operations Agent Tuning, Stage 2 (Agent System Prompt)

**Date:** 2026-07-29
**Type:** Backend — agent system prompt + config-driven persona/currency (mock-first)
**Program:** WhatsApp Operations Agent tuning. **Stage 2 of 7** (Stage 1 = rules & config layer).

## Objective
Assemble the agent's persona (spec §1), the happy-path order flow (spec §2.12), and the
AED/QAR country overlay (spec §8) into the base system prompt, **pulling live values from
config** (Stage 1's `config/persona.json` + `config/markets.json`). Keep it short and
unambiguous. Discounts are intentionally left untouched (Stage 3's atomic negotiation swap).

## What was built

### Persona (spec §1) — config-driven, safe placeholder handling
- **`rules.py`**: new cached accessors `persona()`, `persona_name() → (name, is_placeholder)`,
  `persona_languages()` reading `config/persona.json`.
- **`booking_tools.py` `_persona_intro()`** (new) + prompt header: states the single agent
  name **only when the founder has set it**; while it is a placeholder (spec §13) the agent
  speaks as "a member of the Laundry Khalas team" and **never invents a name**. Adds
  "never reveal or imply you are an AI" and the **English/Arabic** language instruction
  (reply in the customer's language; other languages best-effort → clear English).
- **`prompts.py` `build_system_prompt()`** (legacy Q&A path) given the same persona name +
  never-reveal-AI + language line for consistency.

### Currency / market overlay (spec §8)
- **`_clock_block()`** (the backend-authoritative per-turn state block, already merged into
  every booking turn) now also carries `market`, `currency`, `pricing_configured` via
  `services/market.py`.
- **`services/market.py`**: `get_market()` now normalises market spellings
  (`UAE`/`Dubai`/`Qatar`/`Doha` → `AE`/`QA`), mirroring `services/clock.py`, because the
  customer row stores `market` in mixed forms.
- **Prompt** instructs: quote/take payment ONLY in the customer's currency; never mix
  currencies; if `pricing_configured=false` (e.g. Qatar/QAR — not yet priced) do **not**
  quote — say a specialist will confirm and call `request_human_support`.

### Order flow (spec §2.12) added to the prompt
Wash & Fold vs Clean & Press disambiguation; **photo-gate before quoting specialty items**
(shoes, bags, carpets, curtains, soft toys, alterations); alterations require sample garment
OR exact measurements with **cm-vs-inch confirmation**; full address + building/villa/flat +
**room number for hotels** + name (= order ref) before confirming; driver contacts **15–30 min
before**, proof photo, **reception/security/at-door** fallbacks with "don't assume reception is
allowed / driver won't enter empty premises"; capture **special-care notes** via
`save_special_instructions`; free pickup/delivery with any small-order fee shown by the summary
(never invented); steer to pickup over walk-ins.

### Payment guardrails (spec §2.6 / §6)
Prefer secure card payment; **cash on collection accepted** if the customer prefers (never lose
an order over method); **do NOT create/promise a payment link** in-agent; **NEVER arrange cash
off-system with the driver**.

## Files created
- `apps/whatsapp-agent/tests/test_agent_prompt_persona.py`

## Files modified
- `apps/whatsapp-agent/rules.py` (persona accessors)
- `apps/whatsapp-agent/agents/whatsapp_agent/booking_tools.py` (`_persona_intro`, prompt flow/currency/payment, `_clock_block` market fields)
- `apps/whatsapp-agent/agents/whatsapp_agent/prompts.py` (persona/language in legacy prompt)
- `apps/whatsapp-agent/services/market.py` (spelling normalisation)

## API / DB / UI / integrations
- **None.** No endpoints, migrations, UI, or integrations changed. No new tools (Stage 3).

## What is mock-only / live / deferred
- **Mock-only:** all under `LLM_PROVIDER=mock`. No live WhatsApp/LLM/Stripe touched.
- **Behaviour change:** the agent now speaks with the persona/flow/currency guidance in its
  prompt. It still uses the existing tools — no min-order-fee tool, no express-surcharge tool,
  no negotiation ladder yet (Stage 3), so it will not state a delivery fee or ladder discount
  until those tools land; the prompt is written to defer those numbers to the summary/tools.
- **Deferred:** negotiation wiring + auto-discount retirement (Stage 3); villa/wedding/couture
  routing (Stage 4); privacy tests (Stage 5); §12 regression scenarios + replay (Stage 6).

## Tests run
```
cd apps/whatsapp-agent
./.venv/Scripts/python.exe -m pytest tests/test_agent_prompt_persona.py tests/test_market.py -q
./.venv/Scripts/python.exe -m ruff check rules.py services/market.py agents/whatsapp_agent/{prompts,booking_tools}.py tests/test_agent_prompt_persona.py
./.venv/Scripts/python.exe -m pytest tests/test_booking_tools.py tests/test_booking_flow.py \
  tests/test_pickup_scheduling.py tests/test_human_intervention.py tests/test_webhook.py \
  tests/test_anthropic_tool_loop.py tests/test_webhook_delivery.py -q
```
## Test results (honest)
- New persona/prompt + market suite: **25 passed** (incl. placeholder-name-never-leaks and
  real-name-is-used).
- ruff on all changed files: **All checks passed**.
- Regression (booking, scheduling, intervention, webhook, anthropic loop): **97 passed**
  across those files. Full suite not run (README: large; run targeted files).

## Acceptance criteria
1. ✅ Single persona from config; placeholder name never surfaces; real name used when set.
2. ✅ Never-reveal-AI + English/Arabic language policy in the prompt.
3. ✅ AED/QAR overlay: quote in the customer's currency, never mixed; unpriced market → human.
4. ✅ §2.12 flow (photo-gate, address capture, driver expectations, special-care, alterations
   cm/inch) and payment guardrails (card-first, cash fallback, no driver side-deal, no link).
5. ✅ Additive & non-breaking — all touched regression suites green.

## Known limitations / next steps
- `agent_name` remains a **placeholder** — founder to set (spec §13); QAR still routes to human
  until a Qatar price list exists.
- **Next: Stage 3** — tool-gating: expose the negotiation ladder + facility-floor, min-order
  delivery fee, and express surcharge as authority-gated tools; wire them in and **atomically
  retire the automatic 15%-over-100 discount** (founder decision), updating its tests.
