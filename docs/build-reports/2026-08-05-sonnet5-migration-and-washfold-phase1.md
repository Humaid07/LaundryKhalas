# Build Report — WhatsApp Agent Production Update, Phase 1 (Sonnet 5 + Wash & Fold)

**Date:** 2026-08-05
**Status:** Phase 1 complete, full backend suite green (1353 passed). UNCOMMITTED.

## 1. Objective
Begin the large 2026-08-05 WhatsApp production update (~30 spec sections). Owner chose
**"foundation first, phased"**. Phase 1 delivers the two headline, lowest-risk,
fully-testable foundations: the model migration (Section 1) with correct request
config + usage recording (Section 2), and the deterministic Wash & Fold pricing
correction + optimizer (Section 18 / §30 test matrix). Later sections are deferred
(see §15).

## 2. What was built / changed
### Model migration (Section 1)
- Primary WhatsApp model **Haiku 4.5 → `claude-sonnet-5`**, centralised in the single
  knob `ANTHROPIC_WHATSAPP_MODEL` (`settings.anthropic_model_effective` unchanged as the
  one resolution point). The live `.env` previously held an invalid `claude-sonnet` id —
  corrected to `claude-sonnet-5`.
- New config: `ANTHROPIC_WHATSAPP_EFFORT=high`, `ANTHROPIC_WHATSAPP_THINKING_MODE=adaptive`,
  `ANTHROPIC_WHATSAPP_THINKING_DISPLAY=omitted`, `ANTHROPIC_FALLBACK_ENABLED=false` +
  `ANTHROPIC_FALLBACK_MODEL=` (explicit, disabled — **no silent fallback to Haiku or
  another Sonnet**), `WHATSAPP_SERVICE_RULESET_VERSION=2026_08_05`.
- Provider request correctness (`llm/providers/anthropic.py`): for the adaptive-thinking
  family (Sonnet 5 / Opus 4.6+ / Fable 5, reusing `_NO_SAMPLING_PARAMS` as the single
  gate) the request now sends `output_config={"effort":"high"}` and
  `thinking={"type":"adaptive","display":"omitted"}` and **no** `temperature`/`top_p`/
  `top_k`/manual thinking budget (all 400 on Sonnet 5). Haiku keeps `temperature` and
  **never** receives effort/thinking. Verified against the claude-api skill.
- Existing behaviour retained: `refusal`/`max_tokens`/timeout/rate-limit handling,
  application-controlled idempotent retries, safe deterministic mock fallback.

### Usage recording (Section 2)
- `LLMResult.effort` added; `AgentReply` carries `effort` + `cache_read_tokens` /
  `cache_write_tokens` / `cache_hit`; auto-reply message metadata + booking-orchestration
  log now record effort and cache buckets. Prompt caching (1h system+tools / 5m history)
  was already implemented and tested — unchanged, only instrumented further.
- `settings.ai_status` exposes effort/thinking/fallback/ruleset; `validate_ai_config`
  rejects invalid effort/thinking values and a fallback-enabled-without-id config.

### Wash & Fold pricing (Section 18 / §30)
- Removed the **AED 7 per-additional-kg** rule everywhere → **AED/QAR 12 per kg**; the
  12 kg bag corrected **AED/QAR 80 → 90** (AE catalogue + QA overlay). One source of
  truth (the published catalogue).
- New `services/wash_fold_pricing.py` — deterministic weight optimiser reading prices
  from the catalogue. Cheapest valid combination of 6 kg / 12 kg packages + additional
  kg. Anchored to the published examples: 6→60, 12→90, **13→102, 18→150, 20→180, 24→180**.

## 3. Files
**Modified:** `apps/whatsapp-agent/settings.py`, `llm/providers/anthropic.py`,
`llm/providers/base.py`, `llm/service.py`, `agents/whatsapp_agent/agent.py`,
`agents/whatsapp_agent/booking_tools.py`, `api/evolution_webhooks.py`,
`config/laundry_catalogue.json`, `config/laundry_catalogue_qa.json`, `.env`, `.env.example`,
`tests/test_whatsapp_model_selection.py`, `tests/test_catalogue_pricing.py`,
`tests/test_qa_pricing.py`.
**Created:** `services/wash_fold_pricing.py`, `tests/test_wash_fold_optimizer.py`.

## 4. Mock-only / live / deferred
- **Mock-only:** all tests run offline (mock provider / scripted fake Anthropic). No live
  LLM/WhatsApp/Stripe calls.
- **Live effect on deploy:** the Sonnet 5 config becomes active wherever `ANTHROPIC_*`
  env is applied; the catalogue value change needs a **prod Supabase reseed**
  (`scripts/seed_service_catalogue.py`) since the DB catalogue is the runtime source of
  truth in Supabase mode.
- **Deferred (NOT built this phase):** min-order/delivery (AED/QAR 30 free + 10 fee — still
  50/8), Express 8–12h / 3 PM wording, Stripe-first + cash flow, payment / quote-inactivity
  / website-abandonment follow-up schedulers (no scheduler infra exists yet), lifecycle
  classification literals, remaining ~13 service-category rule rewrites, dashboard fields,
  and wiring the Wash & Fold optimiser into the booking tool surface.

## 5. Tests
- `pytest` (full suite, hermetic sqlite + mock): **1353 passed, 0 failed** (~5m46s).
- New: `test_wash_fold_optimizer.py` (published matrix + no-AED-7 + QA + fractional).
- Updated fixtures for the Sonnet 5 runtime premise and the new Wash & Fold prices.

## 6. Security / privacy notes
- **Committed live secrets remain in `apps/whatsapp-agent/.env`** (real `ANTHROPIC_API_KEY`
  line 20, plus Supabase DB password / Evolution key / R2 secret). Flagged, **not modified**.
  Owner must rotate and gitignore. No new secrets introduced; `ai_status`/validation never
  echo the key. Customer reasoning is kept internal (`thinking display=omitted`).

## 7. Next recommended step
Phase 2: minimum-order + delivery-charge (AED/QAR 30 / 10) with fixture updates, then the
Stripe-first + cash payment flow and the centralized follow-up scheduler (largest greenfield
build). Wire the Wash & Fold optimiser into a `calculate_wash_fold_package_price` booking tool.
