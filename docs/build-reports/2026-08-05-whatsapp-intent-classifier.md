# Build Report — WhatsApp Intent Classifier (Stages 1–2)

**Date:** 2026-08-05
**Module:** WhatsApp Operations Agent — internal intent classifier
**Status:** Stage 1 (shadow) + Stage 2 (observability + correction UI + routing gate,
flag-off) complete + tested. Live routing activation + eval dataset deferred.

> **Stage 2 addendum** (see §19 at the end): admin classifier panel + Operations
> correction, backend read/correction endpoints, and a flag-gated routing gate
> that changes NOTHING until `WHATSAPP_CLASSIFIER_ALLOW_ROUTING=true` and shadow
> mode is off. Live-customer behavior is unchanged in this increment.

## 1. Objective
Implement the previously-deferred WhatsApp intent classifier end-to-end and
integrate it into the existing agent pipeline as an **internal routing component**
— it never messages the customer, never prices/discounts/schedules, and never
performs a route (it recommends; the backend validates). Runs on its own,
independently-configurable Anthropic model, separate from the customer-facing
Sonnet agent, as a single strict structured call with no tool loop.

## 2. Existing classifier code found
None in the live tree. The old `app/agents/classifier/` was archived empty
(commit `a1a8268`); `docs/architecture/classifier-agent.md` describes it as design
reference only. No `whatsapp_message_classifications` table, no intent columns on
`messages`/`conversations`. Built fresh, reusing the deterministic pattern of
`services/abuse_classification.py` and the catalogue/service-resolution vocabulary.

## 3. Architecture implemented
New self-contained package `apps/whatsapp-agent/classifier/`:

| File | Responsibility |
|---|---|
| `taxonomy.py` | All closed vocabularies (intents, goals, routes, services, pricing/payment/repair/complaint, sentiment, urgency, clarification, human reasons, reason codes, lifecycle) — **stable-ordered** for prompt-cache reuse |
| `schema.py` | `Classification` dataclass + `CLASSIFIER_TOOL_SCHEMA` (JSON Schema for forced tool) + strict validation that repairs out-of-taxonomy values to safe defaults |
| `context.py` | `ClassifierInput` — the compact, PII-safe payload (the only thing the model sees) |
| `prompt.py` | Stable cacheable system prompt (instructions + taxonomy + alias hint) + dynamic per-turn payload |
| `deterministic.py` | Pre-LLM terminal decisions (location, known interactive payload, exact opt-out, explicit human request, empty turn) — no model call |
| `rule_engine.py` | Deterministic keyword classifier — the offline test oracle + failure fallback |
| `lifecycle.py` | Backend-resolved customer lifecycle (never invented by the model) |
| `service.py` | `classify_turn` orchestrator: deterministic → live Sonnet-5 → rule engine; confidence policy |
| `router.py` | `select_route` — recommend-only, validates mandatory-human/clarification/template precedence |
| `integration.py` | `run_shadow_classification` — the single never-raising pipeline entry point (build payload → classify → route → persist → log) |

Provider/service/config changes:
- `llm/providers/anthropic.py` — new `complete_structured()` (single forced-tool
  call via `tool_choice`, reuses existing caching + cost machinery).
- `llm/service.py` — `classify_structured()` + a **separate** cached classifier
  provider (own model, own timeout, 1 retry, thinking off).
- `settings.py` — `WHATSAPP_CLASSIFIER_*` + `ANTHROPIC_CLASSIFIER_MODEL` config,
  `classifier_model_effective` property, `ai_status.classifier`, validation.

## 4. Files changed
**New:** `classifier/{__init__,taxonomy,schema,context,prompt,deterministic,rule_engine,lifecycle,service,router,integration}.py`;
`db/repositories/classifications_repo.py`;
`supabase/migrations/20260805_000039_whatsapp_message_classifications.sql`;
`scripts/{apply,verify}_whatsapp_message_classifications.py`;
`tests/test_classifier.py`; `tests/test_classifier_provider_and_persistence.py`.
**Edited:** `settings.py`, `llm/service.py`, `llm/providers/anthropic.py`,
`api/evolution_webhooks.py` (one fail-open shadow hook).

## 5. Database migration
`whatsapp_message_classifications` (migration 000039): one row per classified
logical turn. Idempotency = `UNIQUE(provider, provider_message_id,
classification_version)` + `on conflict do nothing`. Correction columns
(`corrected_*`) are separate and never overwrite the original. Token/cost/latency
columns mirror `services/metrics.py` key names. RLS deny + service-role bypass,
standard test-data marker columns, `updated_at` trigger. **Written; NOT yet
applied** (apply via `scripts/apply_whatsapp_message_classifications.py` with
`DATABASE_MODE=supabase`; the session's Supabase MCP is read-only by design).

## 6. Classifier model configuration
Independent of the main agent. `ANTHROPIC_CLASSIFIER_MODEL` → default
`claude-sonnet-5` (founder-approved 2026-08-05; downgrade to `claude-haiku-4-5` via
env any time). Single structured call, **no extended/adaptive reasoning** (thinking
off, low effort), `max_tokens=700`, `timeout=2000ms`, one retry, prompt caching on.
The customer-facing model (`ANTHROPIC_WHATSAPP_MODEL`) was **not touched**.

## 7. Prompt + structured schema
Forced single tool `emit_classification` (`tool_choice`), so output is a validated
object — no free-form JSON parsing, no regex recovery. System prompt (taxonomy +
rules + alias hint) is byte-stable → 1h prompt cache; the per-turn payload is the
only dynamic part → cheap repeat calls. Usage recorded: input/output tokens, cache
read/creation, cost, latency, model, status, confidence, version.

## 8. Taxonomy / service taxonomy
Full spec taxonomy implemented (42 primary intents, 20 goals, 6 routes, 26
templates, 21 service domains, pricing/payment/repair/complaint sub-intents,
sentiment/urgency, 12 clarification topics, 19 human reasons, 5 lifecycle stages,
reason codes). Service rules honored: dry-cleaning→CLEAN_AND_PRESS, ironing→
PRESS_ONLY, repair never auto-UNSUPPORTED, non-laundry repair→UNSUPPORTED.

## 9. Integration points
- **Customer lifecycle** — resolved by the backend from persisted facts
  (`lifecycle.py`), passed INTO the payload; never invented by the model.
- **Deterministic pre-classification** — `deterministic.preclassify` short-circuits
  location/known-payload/opt-out/human-request/empty before any model call.
- **Message aggregation** — the hook consumes the existing `CombinedTurn` (one
  logical turn), so fragments are classified once, not per webhook.
- **Router** — `select_route` recommends; mandatory-human and clarification
  override the model's route; unvalidated model "human" is downgraded.
- **Main Sonnet integration** — `Classification.main_agent_hint()` is the compact
  projection ready to pass to the main agent (consumed in Stage 2).
- **Human intervention** — mandatory reasons flagged; deterministic layer +
  router enforce escalation independent of the model.
- **Payment/discount** — detects Stripe vs cash vs dispute and price pushback /
  discount asks WITHOUT computing any discount (backend engine owns that).
- **Repair** — item/scope classified; price/photo/facility decisions left to
  backend service rules.
- **Follow-up cancellation** — `should_cancel_followups=true` on genuine replies
  (the backend decides which jobs to cancel; wiring is Stage 2).

## 10. Observability
No Langfuse exists in this repo; integrated into the existing `structlog` +
message-metadata + `services/metrics.py` sink (spec allows "or the existing
system"). Emits a `classification_completed` event with safe metadata only (no
phone/address/PII); usage keys match what `metrics.py` already aggregates.

## 11. Shadow rollout + flags
Stage 1 default: `WHATSAPP_CLASSIFIER_ENABLED=true`,
`WHATSAPP_CLASSIFIER_SHADOW_MODE=true` — classify + persist + log, production
routing unchanged. Flags for staged rollout / instant rollback (no DB change):
`WHATSAPP_CLASSIFIER_ALLOW_ROUTING`, `WHATSAPP_CLASSIFIER_ALLOW_HUMAN_ESCALATION`,
`WHATSAPP_CLASSIFIER_LOG_CORRECTIONS`.
- **Stage 2:** enable routing for low-risk categories (greeting/service/process/
  address/slot-enquiry/payment-method).
- **Stage 3:** pricing, pushback, repairs, B2B, status.
- **Stage 4:** human-intervention recommendations (only after mandatory-escalation
  tests pass). Deterministic escalation stays active throughout.

## 12. Tests run + results
`./.venv/Scripts/python.exe -m pytest -q` → **1428 passed** (1353 baseline + 75
new). Ruff clean. Classifier tests cover: 29 primary-intent spec cases, service/
repair rules, the `stripe`→`rip` substring regression, pricing/payment, pickup slot
context, multi-intent, contextual short replies, deterministic events, router
precedence, lifecycle, strict schema validation/repair, forced-tool provider path
(offline via injected fake client), persistence no-op in sqlite, and
**mandatory human-escalation recall = 100%** on the approved mandatory set.

## 13. Latency / token / cost
Live path not exercised in CI (no key in tests; mock forced). By construction:
one structured call, no tool loop, ≤700 output tokens, 2s timeout, 1h-cached stable
prefix → the bulk of input tokens are cache-reads (~0.1× cost) on repeat turns.
Offline deterministic path: 0 tokens, 0 cost, sub-ms. Real latency/cost to be
measured against the deferred sanitized eval set once live.

## 14. What is mock / live / deferred
- **Live-capable now:** classifier runs real Sonnet-5 when `live_llm_ready`
  (founder-approved). Falls back to the deterministic rule engine offline/on
  failure. **Shadow mode ON** — does not control routing yet.
- **Deferred (Stages 2–4):** routing activation; main-agent hint consumption;
  follow-up cancellation wiring; admin dashboard classifier panel + Operations
  correction UI/endpoint; sanitized historical eval dataset + accuracy scoring;
  migration application to Supabase.

## 15. Security / privacy
Payload is PII-safe by construction (no full phone/address/coords/payment links/
history/margins). Logs carry safe metadata only. Classifier can't send messages,
call DB tools, or price. Mandatory escalation enforced deterministically, not on
model say-so alone.

## 16. How to verify manually
- `GET /api/settings/status` → `ai_status.classifier` shows model/flags/live_ready.
- With `DATABASE_MODE=supabase`, apply + verify:
  `python scripts/apply_whatsapp_message_classifications.py` then
  `python scripts/verify_whatsapp_message_classifications.py`.
- Send a WhatsApp turn (test number) → a `classification_completed` structlog line
  appears and a row lands in `whatsapp_message_classifications` (shadow_mode=true).

## 17. Known limitations
- Live-model accuracy is not yet measured against a labelled set (eval harness is
  Stage 2). The rule-engine oracle validates plumbing + taxonomy, not the LLM.
- Migration not applied (read-only Supabase MCP; apply via CLI/script).
- Meta webhook path (`api/webhooks.py`) is not wired to the classifier — only the
  canonical Evolution pipeline (`api/evolution_webhooks.py`).
- Shadow-comparison reporting (classifier route vs production route) records both
  but the comparison dashboard is Stage 2.

## 18. Next recommended step
Apply migration 000039 to dev/test Supabase, run one live shadow turn, confirm a
persisted row + `classification_completed` event, then start Stage 2 (dashboard
panel + low-risk routing) behind `WHATSAPP_CLASSIFIER_ALLOW_ROUTING`.

## 19. Stage 2 — observability + correction + routing gate (flag-off)
**Sequencing note:** actually flipping low-risk routing changes live customer
replies, so it must wait until shadow data exists to validate against. Stage 2
therefore builds the observability + correction layer + the routing *gate* (wired
but OFF), and defers the flag flip.

**Backend** (`api/conversations.py`):
- `GET /api/conversations/{id}/classifications` — per-turn results (empty in
  SQLite mode).
- `POST /api/conversations/{id}/classifications/{cid}/correction` — Operations
  correction, validated against the taxonomy, gated by
  `WHATSAPP_CLASSIFIER_LOG_CORRECTIONS`; writes only `corrected_*` columns (never
  overwrites the original; never reverses a completed side effect).

**Routing gate** (`classifier/router.py::should_route_via_classifier`) — pure
function; returns True only when shadow mode is OFF, routing is enabled, the
intent is in `LOW_RISK_INTENTS` (greeting/service-enquiry/service-selection/
process/address/slot-enquiry/payment-method), confidence ≥ high threshold, and no
human/clarification. It changes nothing on its own — the caller acts on a True
(deferred). Default flags keep it inert.

**Admin UI** (targets the live `:8101` backend):
- `lib/dashboard/whatsapp-agent-api.ts` — `ClassificationDTO` +
  `listClassifications` / `correctClassification`.
- `components/dashboard/operations/live/ClassifierPanel.tsx` — per-turn panel
  (intent, service, confidence, recommended route, sentiment/human/clarify/shadow
  badges, model/status/latency, secondary intents) + inline correction editor
  (primary intent + service domain + reason) with refresh.
- Mounted full-width in `OperationsDeepLink.tsx` (the live conversation detail),
  using the existing `Panel`/`StatusBadge`/`Button`/`EmptyState`/`LoadingState`
  primitives and `useLiveAgentData`.

**Tests:** `tests/test_classifier_api_and_gate.py` — endpoint offline behavior
(empty list; correction requires Supabase → 503) + 6 routing-gate cases.
**Admin:** `tsc --noEmit` exit 0, `next lint` clean.

**Deferred to Stage 2b+ / 3–4:** flip `ALLOW_ROUTING` after shadow data; wire the
gate's True into the webhook; shadow-vs-production comparison view; sanitized
historical eval dataset + accuracy scoring; human-escalation recommendations.

## Related
- `docs/superpowers/specs/2026-08-05-whatsapp-classifier-design.md`
- `docs/architecture/classifier-agent.md` (original design reference)
- `docs/build-reports/2026-08-05-agent-and-dashboard-inventory.md`
