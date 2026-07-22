# Classifier Agent — Architecture

## Role

Per `CLAUDE.md` §9, the Classifier Agent runs **before** the WhatsApp
Operations Agent. It labels every inbound message (intent, sentiment,
sales-stage delta, topic) and derives routing flags (urgency, complaint,
angry, escalation, refund/cancellation, B2B) — it never replies to a
customer, creates an order, or requests approval. It only observes and
writes labels.

## Where it lives

`app/agents/classifier/` in the main system (`app/`), alongside
`app/agents/whatsapp_operations/`. Not part of the separate
`apps/whatsapp-agent/` standalone project (see
`docs/decisions/ADR-standalone-whatsapp-agent-first.md`, which explicitly
scoped the classifier out of that task) - this is the main roadmap's
build-priority-#3 Classifier Agent.

```
app/agents/classifier/
  tools.py    deterministic keyword classifier + routing-flag rules
  prompts.py  the real Section D.4 LLM prompt (not used by the mock path yet)
  agent.py    ClassifierAgent.classify(db, conversation_id) - orchestration
```

## Taxonomy

Adapted from the old prototype's Section D.4 classifier spec
(`Classifier-D4.md` / `00-master-build-spec.md` in
`LaundryKhalasPrototype`), which `docs/audits/prototype-md-review.md`
flagged as "a strong concrete starting point for this repo's
build-priority-#3 Classifier Agent". Reviewed and adapted, not copied
verbatim - see "Deviations from the prototype spec" below.

- **18 intents**: `new_enquiry, quote_request, order_placement,
  order_tracking, complaint, pickup_issue, delivery_issue, payment_issue,
  facility_issue, pricing_objection, cancellation, rescheduling, b2b_lead,
  facility_onboarding, driver_support, lost_lead, repeat_order,
  general_enquiry`
- **5 sentiment categories** (`happy, neutral, frustrated, urgent, angry`)
  plus a numeric score from -1.0 to +1.0
- **Sales-stage delta**: `new_lead, qualified, quoted, follow_up_needed,
  won, lost, no_change`
- **Topic**: a short free-text label

## Why deterministic, not a live LLM call

`tools.classify_text()` is keyword/pattern matching, the same pattern
`whatsapp_operations/tools.py::extract_order_slots` already uses for slot
extraction. This is not "inventing data" in the CLAUDE.md §5 sense (there's
no price or policy to fabricate here), but staying deterministic keeps
classification testable and consistent with the rest of the codebase's
mock-first design.

The classification result is still passed through `llm_service.complete()`
(`app/llm/service.py`) exactly like `whatsapp_operations/tools.py::
draft_customer_reply` passes its deterministically-built reply text through
the same gateway - so every classification is audited (cost/tokens/latency)
identically to a real LLM call would be, and turning on a live provider
later is a one-line change inside `agent.py` (build the prompt from
`prompts.render_classification_prompt()` instead of the JSON dict, parse
`result.text` as JSON instead of trusting the local dict) rather than a
redesign.

`prompts.py` already contains the real, unmodified Section D.4 prompt text
for that future swap.

## Routing flags

`tools.compute_routing_flags()` derives, from intent + sentiment:

| Flag | Rule |
|---|---|
| `is_urgent` | intent is complaint/pickup_issue/delivery_issue/payment_issue/facility_issue, OR sentiment is angry |
| `is_escalated` | sentiment_score <= -0.5 |
| `needs_followup` | intent is quote/pricing/booking/B2B-related |
| `complaint_flag` | same set as `is_urgent`'s intent check |
| `angry_flag` | sentiment == angry |
| `refund_or_cancellation_detected` | intent is cancellation or payment_issue |
| `b2b_enquiry_detected` | intent is b2b_lead or facility_onboarding |

This is CLAUDE.md §9's exact list ("intent, sentiment, urgency, complaint
flag, angry flag, escalation flag, refund/cancellation detection, B2B
enquiry detection"), each one present here.

## Deviations from the prototype spec

- The prototype's routing rules used a 0.0-1.0 sentiment scale; this repo's
  D.4 prompt (and this implementation) uses -1.0..+1.0, so the `< 0.5` /
  `< 0.2` thresholds were re-derived as `<= -0.5` / `<= -0.8` here (see
  `Classifier-D4.md`'s own note that the old thresholds "were written
  against the *current* placeholder sentiment scale" and would need
  re-deriving for the real D.4 scale - this implementation does exactly
  that).
- The prototype ran classification as an async Celery task. This repo has
  no Celery task wiring yet (`app/tasks/` only has `celery_app.py`, no task
  modules) and everything else in this codebase is synchronous
  request/response. Classification runs synchronously, inline, immediately
  after the inbound message is stored - see "Where it runs" below. Moving
  it to a Celery task later is possible without changing `agent.py`'s
  public interface.

## Where it runs

Wired into `POST /api/mock-whatsapp/inbound`
(`app/api/routes/mock_whatsapp.py`): right after
`mock_whatsapp_adapter.receive_inbound()` stores the message and before the
transaction commits, `classifier_agent.classify()` runs. This guarantees
classification has already happened by the time an admin later clicks "Run
WhatsApp Agent" (`POST /api/admin/conversations/{id}/run-agent`).

A second, manual entry point exists for testing/demo/reclassification:
`POST /api/admin/conversations/{id}/classify` (`app/api/routes/admin.py`),
requires `X-Admin-Api-Key` like every other admin route.

## How the Operations Agent reacts to it

As of `docs/build-reports/2026-07-18-classifier-escalation-wiring.md`, the
two agents are coupled: `app/agents/whatsapp_operations/graph.py`'s
`decide_next_action` node checks `tools.requires_escalation(latest_intent,
latest_urgency)` (`app/agents/whatsapp_operations/tools.py`) before
attempting slot extraction. If the classifier flagged the conversation as
urgent/escalated (by sentiment) or the intent is one this agent has no tool
for (`complaint, pickup_issue, delivery_issue, payment_issue,
facility_issue, pricing_objection, cancellation, rescheduling, b2b_lead,
facility_onboarding, driver_support, lost_lead`), the agent skips the
happy-path flow entirely and sets `decision = "escalate"` with
`error = "classifier_flagged_intent=<intent>"` - which then flows through
the *existing* escalation machinery unchanged (`safety_filter` →
`draft_reply`'s `render_escalation_notice` → `create_approval`'s
`tools.escalate_to_human`, whose `reason` becomes exactly that error
string, visible on the resulting `HumanApproval.reason`).

This closes a real bug found while wiring it up: without this check, a
message like *"please reschedule my wash and fold pickup to tomorrow
afternoon, Marina"* contains all three order slots
(service_type/area/pickup_when) and would have been treated as a brand new
order request - creating a **duplicate order** instead of recognizing the
customer wanted to change an existing one. `app/tests/
test_classifier_escalation.py::test_reschedule_request_escalates_instead_of_duplicate_order`
guards this specifically.

`decide_next_action` reads `latest_intent`/`latest_urgency` off `AgentState`
(populated by `load_conversation_context` from the `Conversation` row, the
same columns the classifier writes) rather than re-querying - no new DB
call. The check is placed in `decide_next_action`, not
`load_conversation_context`, deliberately: an earlier return from
`load_conversation_context` (mirroring the existing `manual_takeover`
short-circuit there) would skip populating `market_id`/`customer_id` in
state, and `draft_reply` unconditionally reads `state["market_id"]` -
placing the check after that data is loaded avoids a `KeyError`.

## Data model - no migration

No new tables or columns. `Conversation.latest_intent`,
`latest_sentiment`, `latest_urgency` were placeholder columns already on
the model (added and documented as "for future classifier agent, not built
in this task" during the WhatsApp Agent backend build) - this task
populates them for the first time. `latest_urgency` collapses the full flag
set into one of `urgent` / `escalated` / `normal`
(`tools.latest_urgency_label()`) since the column is a single free-form
`String(32)`, not a flag set.

The full flag set (all 7 CLAUDE.md §9 fields, plus `sentiment_score`,
`sales_stage_delta`, `topic`) is not persisted as new columns - it lives in
`AIActionLog.output_json` for the `action_type="classify"` row, the same
place every other agent decision in this system is audited. Adding
dedicated columns/tables for these was deliberately not done (see
`docs/decisions/classifier-agent-design-decisions.md`) - the smallest safe
version first, per `CLAUDE.md` §16.

## What is NOT done here

- No Admin UI change. `ConversationRead` already exposed `latest_intent`/
  `latest_sentiment`/`latest_urgency` in its schema (unused placeholders
  until now); `apps/admin/lib/types.ts` already types them; no
  component in `apps/admin/` renders them yet. Surfacing them (a badge on
  the conversation list, an urgency filter) is a small, contained frontend
  task, not done here since it wasn't asked for.
- No Celery/async wiring - see "Deviations from the prototype spec" above.
