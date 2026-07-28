# Build Report — Abuse-triggered human intervention (full stateful feature)

**Date:** 2026-07-28
**Area:** `apps/whatsapp-agent` (classification, webhook, state, API) + `apps/admin` (Operations queue)
**Migration:** `000028_human_interventions` (applied to dev/test Supabase)

## Existing architecture found (audit)
The AI-pause + human-reply plumbing already existed and was reused, not rebuilt:
- `conversations.status = 'human_takeover'` already pauses the AI — the webhook stores-only for
  those conversations (`evolution_webhooks.py` gates + store branch) and turn-recovery skips them.
- `POST /api/conversations/{id}/human-message` already stores the operator reply **and sends it
  via Evolution** (`send_status`), plus `human-takeover` / `return-to-bot` / `resolve` endpoints.
- Escalation (keyword) → flags/tickets/complaints; inbound + outbound message idempotency.

The gaps this build closes: (1) structured abuse/threat **classification**, (2) wiring it into the
aggregated turn to **pause before** a holding message, (3) a **rich persistent intervention state**
+ Operations **queue**, concurrency-safe **claim**, **release-to-AI**, permissions, audit, metrics.

## Abuse classification approach + deterministic rules
`services/abuse_classification.py` (pure, config-driven `config/abuse_rules.json`) is the
**authoritative** enforcement layer (Claude may propose, but this decides). `classify(text,
prior_abuse_event_count)` returns the full structured result: `customer_sentiment`, `anger_level`,
`abuse_detected`, `abuse_category`, `abuse_target`, `threat_detected`, `threat_severity`,
`human_intervention_required`, `confidence`, `reason_codes`, `customer_safe_response_type`,
`recommended_priority`. Deterministic rules distinguish:
- Dissatisfaction ("expensive", "terrible service", "nobody replied") → negative, **no takeover**.
- Profanity *about the service* ("this fucking service is slow") → GENERAL_PROFANITY, **no takeover**
  (until it repeats past a threshold).
- Profanity/insult *at a person* ("you are a fucking idiot") → DIRECT_INSULT → takeover.
- Slurs → HATE_OR_SLUR; sexual harassment → SEXUAL_HARASSMENT; threats to staff/driver/facility
  ("I'll hurt the driver", "I'll come there") → THREAT with HIGH/IMMINENT severity, CRITICAL.
- Repetition across the aggregated turn / prior events → REPEATED_ABUSE / SEVERE_HOSTILITY.
Runs inline on the combined turn — **no extra LLM call** for abuse detection.

## Anthropic prompt changes
Added a "Staying calm under anger" block to `booking_system_prompt()`: remain calm, never mirror
abuse, never argue/shame/lecture, never say "calm down / I am an AI / you were flagged"; treat
ordinary dissatisfaction as a normal complaint. Defense-in-depth — the backend gate intercepts real
abuse **before** Claude is ever called.

## Database model + AI pause
Migration `000028` adds `human_interventions` (lifecycle: `takeover_status`
WAITING_FOR_HUMAN→ASSIGNED→HUMAN_ACTIVE→RESOLVED/RELEASED_TO_AI/CLOSED, `takeover_reason`,
`abuse_category`/`abuse_target`/`threat_severity`/`confidence`/`reason_codes`, `internal_priority`,
`flagged_message_id`/`flagged_turn_id`/`sanitized_preview`, `assigned_agent_id`, notice + all
timestamps) plus `conversations.takeover_reason`/`takeover_status`. A **partial-unique index**
(one active row per conversation) is the idempotency backbone. The **AI pause reuses the existing
`human_takeover` status gate** — `create_and_pause` sets it in the same transaction.

## Workflow-state changes / ordering
`db/repositories/human_interventions_repo.create_and_pause` runs INSERT(intervention) +
UPDATE(conversation → human_takeover) in **one transaction** (`SELECT … FOR UPDATE` then insert),
committed **before** the holding message is sent (`services/human_intervention.py`). A concurrent
later message re-reads `human_takeover` and is stored, never answered.

## Operations queue + assignment + reply + release
- **Queue:** `GET /api/human-intervention/queue` (filters: status/reason/severity/agent/market),
  `GET /metrics`, `GET /{id}`. PII-safe (masked phone + sanitized preview; full text only in the
  authorized conversation view). Admin page `operations/human-intervention` (+ nav entry) — priority/
  severity/reason badges, waiting time, unread, **Claim** / **Open** / **Release to AI**, 15s poll.
- **Claim:** `POST /{id}/claim` — atomic `UPDATE … WHERE assigned_agent_id IS NULL RETURNING`, so two
  agents can't both own it (2nd gets 409).
- **Reply:** reuses the existing `POST /api/conversations/{id}/human-message` (stores + sends via
  Evolution, `send_status` surfaced) — **not** routed through Claude; AI stays paused.
- **Resolve:** `POST /{id}/resolve` — does NOT resume AI.
- **Release to AI:** `POST /{id}/release-to-ai` — explicit, sets RELEASED_TO_AI + resumes automation
  (`return_to_bot`); **severe threats (HIGH/IMMINENT) require an admin (supervisor)**.

## Permissions / notifications / audit / metrics
- Router gated by `require_ops` (admin+operations); severe-threat release gated to `admin`.
- Notifications: the queue row + `operations_notification_created` / `severe_threat_flagged`
  structured events (no external dependency added).
- Audit: structlog events `abuse_classification_completed`, `human_intervention_created`,
  `automation_paused`, `human_intervention_notice_sent` / `_duplicate_prevented`,
  `conversation_claimed`, `human_intervention_resolved`, `conversation_released_to_ai`,
  `severe_threat_flagged` — safe ids only (no phone/address/full abusive text).
- Metrics: `/metrics` (total/waiting/human_active/resolved/released/threats/abusive/critical/
  avg-seconds-to-accept).

## Tests & results
- `tests/test_abuse_classification.py` — **18** (classification matrix). `tests/test_human_intervention.py`
  — **7** (trigger only on abuse/threat, one holding message, duplicate prevented, no-trigger on
  dissatisfaction/clean). 114 booking/scheduling regressions pass; ruff clean; admin `tsc` clean.
- **Live dev-Supabase smoke:** idempotent create (same event on re-trigger), conversation paused,
  notice-once, concurrency-safe claim (A wins / B 409), release-to-AI. **Webhook `_process_reply`
  end-to-end:** abusive turn → pause + intervention + **no booking draft**; second abusive turn →
  reused + notice-duplicate-prevented, count stable 1→1.

## Manual verification
1. Backend on Supabase; send an abusive WhatsApp turn from an approved number → conversation moves to
   `human_takeover`, one holding message, a row in Operations → Human Intervention.
2. A later normal message → stored, unread++, **no AI reply**.
3. Claim in the dashboard → status HUMAN_ACTIVE; reply from the conversation view → sent via Evolution.
4. Release to AI → automation resumes.

## Known limitations / policies to confirm
- English-only term lists (Arabic/mixed-script pending); slur/sexual lists deliberately conservative.
- Pending-messages-on-release "handled vs re-queue" decision is not yet a UI step (release resumes AI;
  the human sees the messages in-thread first) — a small follow-up.
- Notifications are in-dashboard + logs (no email/Slack unless already configured).
- Business policy to confirm: human-response SLA wording, supervisor role for severe-threat release
  (currently admin), whether general profanity should ever auto-pause (currently only after 3 repeats).
- No law-enforcement/emergency automation (per spec).
