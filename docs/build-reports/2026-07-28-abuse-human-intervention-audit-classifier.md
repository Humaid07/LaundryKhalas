# Build Report — Abuse-triggered human intervention: audit + deterministic classifier (slice 1)

**Date:** 2026-07-28
**Area:** `apps/whatsapp-agent` (escalation / classification)
**Status:** Slice 1 of a multi-slice feature — **audit complete + classification engine built & tested**. Stateful wiring / dashboard / permissions slices are **staged** (see §Deferred) because the wiring point is being edited by a concurrent session and needs a schema-migration decision.

## 1. Existing architecture found (audit)
Much of the human-intervention plumbing already exists:
- **AI pause** — the `human_takeover` conversation status already halts the AI. The webhook
  gates the Anthropic/booking turn with `convo.status != "human_takeover"`
  (`api/evolution_webhooks.py:719-720, 752-753`); such convos hit a **store-only** branch
  (`:785`) and turn-recovery skips them (`:109-111`). So an inbound message during takeover is
  stored, not answered by the AI.
- **Dashboard human reply via Evolution** — `POST /api/conversations/{id}/human-message`
  (`api/conversations.py:76-105`) stores the operator reply **and sends it through Evolution**,
  returning a `send_status` (`sent` / `send_failed` / `stored`).
- **Takeover / release / resolve** — `POST .../human-takeover`, `.../return-to-bot`,
  `.../resolve` (`api/conversations.py`), backed by `conversations_repo`.
- **Escalation → flags/tickets/complaints + `human_needed`** — `services/escalation.py`
  (keyword) + webhook handling (`:672`), plus `complaints`/`pending_tasks`.
- **Idempotency** — inbound `wa_message_id`; outbound reply key `sha1(turn_id|state|body)` in
  `messages.metadata` (added by a concurrent session's latest build).

### What was genuinely missing
1. **Abuse/threat classification** — `escalation.py` only matches refund/complaint/damage
   keywords; there was **no** structured abuse/threat classifier and **no** distinction between
   genuine abuse and ordinary dissatisfaction. ← built in this slice.
2. Wiring the classifier into the aggregated-turn processor to set takeover + reason/severity +
   **one idempotent holding message** (staged — see §Deferred).
3. Rich intervention **state** (reason/category/severity/priority/assigned/timestamps) beyond the
   bare status; Operations **queue** UI; concurrency-safe **claim**; granular **permissions**;
   **notifications/audit/metrics** (staged).

## 2. What was built this slice
- **`services/abuse_classification.py`** — pure, config-driven, deterministic classifier.
  `classify(text, prior_abuse_event_count=0)` returns an `EscalationClassification` with:
  `customer_sentiment`, `anger_level`, `abuse_detected`, `abuse_category`, `abuse_target`,
  `threat_detected`, `threat_severity`, `human_intervention_required`, `confidence`,
  `reason_codes`, `customer_safe_response_type`, `recommended_priority`. Plus
  `intervention_reason()` → `ABUSIVE_LANGUAGE` / `THREAT` / None.
  - Categories: NONE / GENERAL_PROFANITY / DIRECT_INSULT / DEROGATORY_LANGUAGE / HATE_OR_SLUR /
    SEXUAL_HARASSMENT / THREAT / REPEATED_ABUSE / SEVERE_HOSTILITY.
  - Targets: BUSINESS / AI_AGENT / HUMAN_STAFF / DRIVER / FACILITY / … . Threat severities:
    NONE→IMMINENT.
  - **Key distinctions:** profanity *about the service* ("this fucking service is slow") →
    GENERAL_PROFANITY, **no takeover**; profanity/insult *at a person* ("you are a fucking
    idiot") → DIRECT_INSULT, **takeover**; dissatisfaction ("expensive", "terrible", "nobody
    replied") → NEGATIVE sentiment, **no abuse, no takeover**; threats to staff/driver/facility →
    THREAT, immediate takeover, CRITICAL. Repetition across the aggregated turn / prior events
    escalates to REPEATED_ABUSE / SEVERE_HOSTILITY.
  - Backend-authoritative: designed so a Claude-proposed classification can be cross-checked /
    overridden by this deterministic layer, and so **high-confidence severe cases trigger takeover
    without a second model call**.
- **`config/abuse_rules.json`** — term lists (profanity, insults, slurs, sexual, threat verbs,
  presence/imminent phrases, dissatisfaction) + thresholds (repeated=2, severe=3, general-profanity
  intervention-after=3). Single source of truth; no hardcoded terms in code.

## 3. Tests & results
- **`tests/test_abuse_classification.py` — 18 tests, all pass**, ruff clean. Mirrors the spec
  matrix: dissatisfaction (5 msgs) → no takeover; general profanity → not takeover; repeated
  profanity → escalates; direct insult → takeover + AI_AGENT target; staff insult → HUMAN_STAFF;
  slur → HATE_OR_SLUR/CRITICAL; sexual harassment → intervention; threat to driver → HIGH/IMMINENT
  + CRITICAL; imminent "come there" threat; property threat; aggregated abusive turn → one
  classification (threat dominates); repeated → REPEATED_ABUSE→SEVERE_HOSTILITY; structured-output
  contract; clean message → neutral.

## 4. Deferred / staged (with reasons)
These are the stateful/UI slices. **Not started** here to avoid clobbering a concurrent session
that is actively editing `api/evolution_webhooks.py` (the wiring point) and because the rich-state
model needs a migration on the drifted shared dev/test Supabase (which I won't apply unilaterally):
- **Slice 2 — Webhook wiring + atomic pause:** run `abuse_classification.classify` on the combined
  turn inside `_process_reply` BEFORE the Anthropic turn; if intervention → transactionally set
  `human_takeover` + persist reason/category/severity + send **one** idempotent holding message
  (key `conversation_id + takeover_event_id + HUMAN_INTERVENTION_NOTICE`) → then commit. Must
  classify → pause → commit → send (never send-then-pause).
- **Slice 3 — Rich intervention state (migration):** `takeover_reason`, `abuse_category`,
  `threat_severity`, `internal_priority`, `assigned_agent_id`, `flagged_at`/`accepted_at`/
  `resolved_at`/`released_to_ai_at`, `customer_notified_at`, notice-sent idempotency, takeover_status
  enum (WAITING_FOR_HUMAN→…→RELEASED_TO_AI).
- **Slice 4 — Operations "Human Intervention" queue** (sanitised previews, priority, filters,
  near-real-time), concurrency-safe **claim** (`UPDATE … WHERE assigned_agent_id IS NULL RETURNING`),
  release-to-AI with pending-message handling.
- **Slice 5 — Permissions** (`conversations.takeover/reply/reassign/resolve/release_to_ai`,
  `human_intervention.view_sensitive/manage`), **notifications**, **audit events**, **metrics**.
- **Prompt:** add the "remain calm, don't mirror abuse, send only the approved transfer message
  when the backend flags intervention, don't resume until released" block (the classifier already
  emits `customer_safe_response_type = TRANSFER_HOLDING`).

## 5. Manual verification (this slice)
`python -m pytest tests/test_abuse_classification.py` (18 pass). Spot-check:
`classify("You are a fucking idiot.")` → DIRECT_INSULT, intervention=True, target=AI_AGENT;
`classify("This fucking service is slow.")` → GENERAL_PROFANITY, intervention=False;
`classify("I will hurt the driver.")` → THREAT, IMMINENT/HIGH, CRITICAL.

## 6. Known limitations / policy to confirm
- English-only term lists; Arabic/mixed-script abuse not yet covered.
- Slur/sexual lists are deliberately conservative (avoid false positives that wrongly pause the AI);
  Operations should expand them from real data.
- Business policy still to confirm: human-response SLA wording, supervisor-gated release for severe
  threats, whether general profanity should ever auto-pause (currently only after 3 repeats).
- No law-enforcement / emergency automation (per spec) — humans decide.
