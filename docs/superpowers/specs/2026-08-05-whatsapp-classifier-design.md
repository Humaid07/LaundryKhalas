# Design — WhatsApp Intent Classifier (Stage 1: Shadow)

**Date:** 2026-08-05 · **Status:** implemented (Stage 1)

## Problem
The roadmap intent classifier was deferred and its old home (`app/`) archived. We
need an internal routing classifier that understands each logical customer turn
(intent, service, lifecycle context, pricing/payment/repair/complaint signals,
human-intervention need, clarification need, multi-intent) without becoming the
source of truth for business rules, and without messaging the customer.

## Key decisions (founder, 2026-08-05)
1. **Live Anthropic approved** for the classifier (overrides mock-first for this
   component). Deterministic rule engine remains as the offline/test + failure
   fallback.
2. **Stage-wise build.** Stage 1 = shadow (classify + persist + log, no routing).
3. **Classifier model = `claude-sonnet-5`**, independently configurable
   (`ANTHROPIC_CLASSIFIER_MODEL`); main agent model untouched.

## Approach
Single **forced-tool** structured call (`tool_choice`) → validated `Classification`
object. Deterministic pre-classification skips the model for unambiguous events.
Backend resolves customer lifecycle from persisted facts. A recommend-only router
validates the route (mandatory-human/clarification/template precedence). Everything
runs behind feature flags for staged rollout + instant rollback.

## Non-negotiables honored
- Never messages the customer; never prices/discounts/schedules; never performs a
  route. PII-safe payload. One call, no tool loop. Idempotent persistence. Prompt
  caching on the stable prefix. Observability via existing structlog/metrics (no
  Langfuse in repo). Deterministic escalation independent of the model.

## Pipeline placement
`evolution_webhooks._process_reply`, after aggregation + state-load + abuse/voice/
escalation gates, immediately before the main Sonnet turn. Fail-open (never raises).

## Data
`whatsapp_message_classifications` (migration 000039), idempotent on
`(provider, provider_message_id, classification_version)`, corrections stored
separately, usage/cost columns aligned with `services/metrics.py`.

## Rollout
Stage 1 shadow (done) → Stage 2 low-risk routing + dashboard panel + eval dataset →
Stage 3 pricing/repair/B2B/status → Stage 4 human-intervention recommendations
(after mandatory-escalation tests pass). Flags:
`WHATSAPP_CLASSIFIER_{ENABLED,SHADOW_MODE,ALLOW_ROUTING,ALLOW_HUMAN_ESCALATION,LOG_CORRECTIONS}`.

Full detail: `docs/build-reports/2026-08-05-whatsapp-intent-classifier.md`.
