# Classifier Agent Design Decisions

- Built inside the main system (`app/agents/classifier/`), not the separate
  `apps/whatsapp-agent/` standalone project - the standalone agent's own
  ADR (`ADR-standalone-whatsapp-agent-first.md`) explicitly scoped the
  classifier out of that task and named it as the natural next step on the
  *main* roadmap (`CLAUDE.md` §18, build priority #3).
- Classification is deterministic (keyword/pattern matching), not a live
  LLM call reasoning freely - consistent with how
  `whatsapp_operations/tools.py::extract_order_slots` already works.
  Classification labels aren't "invented facts" in the CLAUDE.md §5 sense,
  but determinism keeps this testable and avoids introducing
  non-reproducible behavior into an otherwise deterministic mock pipeline.
  The real Section D.4 LLM prompt is written and ready
  (`app/agents/classifier/prompts.py`) for when a live provider is
  approved.
- No new database columns or tables. `Conversation.latest_intent/
  latest_sentiment/latest_urgency` were already on the model as documented
  placeholders for exactly this agent - this task populates them instead of
  adding new schema. The full flag set (urgency/complaint/angry/escalation/
  refund-cancellation/B2B flags, sentiment score, sales-stage delta, topic)
  is derived at classification time and logged in full to
  `AIActionLog.output_json`, not persisted as dedicated columns. If a
  future need arises to filter/query conversations by these flags at the
  database level (e.g., an admin UI "show urgent conversations" filter),
  that's a small additive migration then - not preemptively built now, per
  `CLAUDE.md` §16 ("build the smallest safe working version first").
- Runs synchronously, inline, immediately after `POST
  /api/mock-whatsapp/inbound` stores the message - not as a Celery task.
  The old prototype's spec called for an async Celery task; this repo has
  no Celery task modules wired yet and everything else here is synchronous
  request/response, so matching that existing pattern was chosen over
  introducing async task infrastructure for one agent. `ClassifierAgent
  .classify()`'s interface doesn't assume a caller, so moving it into a
  Celery task later doesn't require a redesign.
- **Update (same day, explicit follow-up request): the WhatsApp Operations
  Agent now reads the classifier's output.** `decide_next_action`
  (`app/agents/whatsapp_operations/graph.py`) escalates instead of running
  the happy-path flow when `tools.requires_escalation(latest_intent,
  latest_urgency)` is true - see `docs/architecture/classifier-agent.md`
  "How the Operations Agent reacts to it" and
  `docs/build-reports/2026-07-18-classifier-escalation-wiring.md`. The
  escalate-on-intent policy (which of the classifier's 18 intents this
  agent has no safe tool for) lives in `whatsapp_operations/tools.py`, not
  `classifier/tools.py` - the classifier stays a general-purpose labeler
  that doesn't need to know which of its labels a particular downstream
  consumer cares about; that policy belongs with the consumer.
- No Admin UI changes. The API already returned these fields (unused
  placeholders); this task makes them real without touching
  `apps/admin/`. Surfacing them visually is flagged as a next step, not
  built here, since it wasn't requested and the task is scoped to the
  agent itself.
