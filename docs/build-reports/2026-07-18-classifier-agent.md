# Build Report: Classifier Agent

## 1. Build title

Classifier Agent (Intent, Sentiment, Routing Flags)

## 2. Date

2026-07-18

## 3. Task objective

Build the Classifier Agent per `CLAUDE.md` §9/§18 (build priority #3 on the
main roadmap): a component that runs before the WhatsApp Operations Agent
and labels every inbound message with intent, sentiment, urgency, complaint
flag, angry flag, escalation flag, refund/cancellation detection, and B2B
enquiry detection - explicitly requested by the founder/team this session,
satisfying §9's "do not build unless explicitly asked" gate.

## 4. What was built

- `app/agents/classifier/` - a new agent module in the main system:
  - `tools.py` - deterministic 18-intent / 5-sentiment classifier
    (`classify_text`) plus routing-flag derivation (`compute_routing_flags`)
    and the `Conversation.latest_urgency` label collapse
    (`latest_urgency_label`).
  - `prompts.py` - the real Section D.4 LLM classification prompt, ready
    for a future live-provider swap, not used by the deterministic path
    yet.
  - `agent.py` - `ClassifierAgent.classify(db, conversation_id)`: loads the
    newest inbound message, classifies it, computes routing flags, passes
    the result through the audited `llm_service.complete()` gateway,
    updates `Conversation.latest_intent/latest_sentiment/latest_urgency`,
    and logs the full result to `AIActionLog`.
- Automatic wiring: `POST /api/mock-whatsapp/inbound` now runs the
  classifier on every stored inbound message, before the transaction
  commits - see `app/api/routes/mock_whatsapp.py`.
- New endpoint: `POST /api/admin/conversations/{id}/classify` - manual
  re-classification, for testing/demo, mirroring how `run-agent` already
  works (`app/api/routes/admin.py`).
- `app/tests/test_classifier_agent.py` - 9 new tests.
- Documentation: this build report, `docs/architecture/classifier-agent.md`,
  `docs/decisions/classifier-agent-design-decisions.md`,
  `docs/presentation-notes/week-01-classifier-agent-demo.md`, plus updates
  to `docs/weekly-reports/week-01-report.md` and `docs/00-Home.md`.

Full design rationale in `docs/architecture/classifier-agent.md` and
`docs/decisions/classifier-agent-design-decisions.md` - not duplicated here.

## 5. Why it was built

Explicit founder/team instruction this session to resume the main roadmap
at build priority #3 (`CLAUDE.md` §18), following the standalone WhatsApp
Agent detour (`docs/decisions/ADR-standalone-whatsapp-agent-first.md`),
which had explicitly deferred the classifier and named it as the natural
next step.

## 6. Files created

- `app/agents/classifier/__init__.py`
- `app/agents/classifier/tools.py`
- `app/agents/classifier/prompts.py`
- `app/agents/classifier/agent.py`
- `app/tests/test_classifier_agent.py`
- `docs/architecture/classifier-agent.md`
- `docs/decisions/classifier-agent-design-decisions.md`
- `docs/build-reports/2026-07-18-classifier-agent.md` (this file)
- `docs/presentation-notes/week-01-classifier-agent-demo.md`

## 7. Files modified

- `app/api/routes/mock_whatsapp.py` - calls `classifier_agent.classify()`
  after storing an inbound message.
- `app/api/routes/admin.py` - added `POST
  /conversations/{id}/classify`.
- `docs/weekly-reports/week-01-report.md` - updated.
- `docs/00-Home.md` - updated to link this report.

## 8. API endpoints added/changed

| Method | Path | Change |
|---|---|---|
| POST | `/api/admin/conversations/{id}/classify` | new |
| POST | `/api/mock-whatsapp/inbound` | unchanged response shape; now also runs the classifier as a side effect before responding |

`ConversationRead`/`ConversationDetail` (`app/schemas/conversation.py`)
were not changed - `latest_intent`/`latest_sentiment`/`latest_urgency` were
already in the schema (unused placeholders); this task is the first thing
that actually populates them.

## 9. Database tables/models added/changed

None. No migration. `Conversation.latest_intent`, `latest_sentiment`,
`latest_urgency` (existing placeholder columns) are now written to. See
`docs/architecture/classifier-agent.md` "Data model - no migration" for why
the fuller flag set was not given new columns.

## 10. UI pages/components added/changed

None. `apps/admin/` was not touched - see §15 and the architecture doc's
"What is NOT done here".

## 11. Agent behavior added/changed

New agent: the Classifier Agent, described above. The existing WhatsApp
Operations Agent's behavior is unchanged - it does not yet consume the
classifier's output (see §15).

## 12. Integrations added/changed

None live. The classifier's LLM-gateway call runs through the same
`llm_service.complete()` path as everything else in this system, which
stays on `MockProvider` unless a live provider is explicitly enabled - it
was not enabled in this task. Verified live-provider-off in test
(`app/tests/test_no_live_calls.py`, still passing, unmodified) and by
inspecting `output_json` on every classify-related `AIActionLog` row
produced during manual verification (§16), which all show
`"provider": "mock"`.

## 13. What is mock-only

Everything. Classification is deterministic keyword matching passed
through the mock LLM gateway for audit-log consistency; no live model call
was made.

## 14. What is live

Nothing.

## 15. What is intentionally deferred

- **Operations Agent does not read classifier output.** The two agents run
  independently today. Wiring the operations agent to branch on
  `is_urgent`/`is_escalated`/etc. (e.g., skip the happy-path flow and
  escalate directly) is a deliberate follow-up, not assumed by this task -
  flagged in `docs/architecture/classifier-agent.md`.
- **No Admin UI surfacing.** `latest_intent`/`latest_sentiment`/
  `latest_urgency` are now real data but nothing in `apps/admin/` displays
  them (a badge on the conversation list, an urgency filter/sort) - not
  built here since it wasn't requested and this task was scoped to the
  agent itself.
- **No Celery/async wiring.** Classification runs synchronously inline on
  the inbound request. The old prototype spec called for an async Celery
  task; this repo has no Celery task modules wired yet, so this follows the
  rest of the codebase's synchronous pattern instead - see the design
  decisions doc.
- **Routing-flag persistence.** The 7 CLAUDE.md §9 flags plus
  sentiment_score/sales_stage_delta/topic are computed and logged, not
  stored as queryable DB columns - a future admin-UI filter ("show me
  urgent conversations") would need a small additive migration then.

## 16. Tests run

1. **Full backend test suite** (31 tests, including the 9 new classifier
   tests) run inside the running `laundrykhalas_api` Docker container via
   `docker compose exec -T api pytest app/tests -q` against the dedicated
   Postgres test database (`conftest.py`'s isolated `<db>_test` pattern) -
   **31 passed, 0 failed**. One collision was found and fixed during this
   session: the new test file initially reused phone numbers already used
   by `test_approval_flow.py` (`+971500000020-022`), which - because
   conversations are keyed by `(market_id, customer_id, status=open)` and
   both test files hit the same phone numbers - caused the new tests to
   observe a conversation shared with another test file's state
   (`assert len(classify_rows) == 1` failed with `2` because the shared
   conversation had already been classified once by the other test's own
   inbound call). Fixed by renumbering the new test file's phone numbers to
   an unused range (`+971500000060-065`) - not a product bug, a test
   fixture collision.
2. **Ruff lint** (`docker compose exec -T api ruff check app/agents/
   classifier app/api/routes/mock_whatsapp.py app/api/routes/admin.py
   app/tests/test_classifier_agent.py`) - one violation found and fixed
   (`F841` unused `recent_messages` variable; resolved by including it in
   the audit log's `input_json` instead of discarding it, since it's
   genuinely useful classification context) - **all checks passed** after
   the fix.
3. **Live smoke test** against the running dev stack (not just the test
   DB), via `POST /api/mock-whatsapp/inbound` with the message "This is
   unacceptable, my order was cancelled without telling me, I am furious":
   - Automatic classification produced `latest_intent: complaint`,
     `latest_sentiment: angry`, `latest_urgency: urgent` on the
     conversation, confirmed via `GET /api/admin/conversations/{id}`.
   - Manual `POST /api/admin/conversations/{id}/classify` re-ran
     classification and returned the full flag set (`is_urgent: true`,
     `is_escalated: true`, `complaint_flag: true`, `angry_flag: true`,
     `refund_or_cancellation_detected: false`, `b2b_enquiry_detected:
     false`).
   - `GET /api/admin/ai-action-logs?conversation_id=...` showed two
     `agent_name: classifier_agent` action pairs (`llm_complete` +
     `classify`) - one from the automatic run on inbound, one from the
     manual re-classify call - each with full input/output JSON, `provider:
     mock`, and non-zero latency, confirming the audit trail works exactly
     like the operations agent's.
4. **No frontend changes** - `apps/admin/` build/typecheck/lint not
   re-run in this task since nothing in that directory changed.

## 17. Test results

All automated tests pass (31/31). Lint clean. Live smoke test behavior
matched expectations for both an order-placement message (`order_placement`
/ `neutral` / `normal`) and a complaint message (`complaint` / `angry` /
`urgent`), confirmed via both the automatic on-inbound path and the manual
`/classify` endpoint.

## 18. Bugs/issues found

- Test phone-number collision between `test_classifier_agent.py` and
  `test_approval_flow.py` - found and fixed during this task (§16 item 1).
- Ruff `F841` unused variable - found and fixed during this task (§16 item
  2).
- No other bugs found. No regressions in the existing 22 pre-existing tests
  (all still pass).

## 19. Known limitations

- Keyword-based classification is a deterministic approximation, not true
  NLU - e.g., sarcasm, negation ("not unhappy"), or intents expressed
  without any of the matched phrases will misclassify or fall through to
  `general_enquiry`/`neutral`. This is explicit, documented mock-mode
  behavior (see `docs/architecture/classifier-agent.md`), not a hidden gap
  - the real D.4 LLM prompt is written and ready for when live
  classification is approved.
- Classifies only the single newest inbound message, not the full
  conversation history - matches the D.4 spec's "classify this message,
  with recent messages as context" design, but means a customer's sentiment
  arc across a long conversation isn't tracked as a trend, only as a
  latest-value snapshot.
- See §15 for the three deliberately deferred integration points (operations
  agent doesn't consume this yet, no Admin UI surfacing, no async/Celery).

## 20. Security/privacy notes

No new PII exposure. The classifier reads message text already stored in
the database (same text the operations agent already reads) and writes
only label strings back - no customer contact info is added to any new
surface. The `/classify` endpoint requires `X-Admin-Api-Key` like every
other admin route (verified in tests: `test_classify_requires_admin_key`).

## 21. Cost/LLM usage notes

Every classification still goes through `llm_service.complete()` and is
cost/token/latency-logged identically to a real call would be, even though
`MockProvider` makes the actual cost `0.0` - this preserves the audit
pattern for when a live provider is turned on later, per `CLAUDE.md` §4/§10
requirements that mock-first must not skip the logging/audit machinery a
live system would need.

## 22. Screens/pages to demo

None (backend-only task). See
`docs/presentation-notes/week-01-classifier-agent-demo.md` for how to
demonstrate this via `curl`/`/docs` today, and what an Admin UI surface
would look like once built.

## 23. Commands to run

```
cd "D:\Laundry Khalas App"
docker compose up -d postgres redis api celery_worker celery_beat
docker compose exec -T api pytest app/tests -q
docker compose exec -T api ruff check app/agents/classifier
```

## 24. How to verify manually

```
curl -X POST http://localhost:8000/api/mock-whatsapp/inbound \
  -H "Content-Type: application/json" -H "X-Admin-Api-Key: <ADMIN_API_KEY>" \
  -d '{"market_code":"AE","phone_number":"+971500009999","message":"This is unacceptable, my clothes are ruined"}'

curl http://localhost:8000/api/admin/conversations/<conversation_id> \
  -H "X-Admin-Api-Key: <ADMIN_API_KEY>"
# -> latest_intent: facility_issue, latest_sentiment: angry, latest_urgency: urgent

curl -X POST http://localhost:8000/api/admin/conversations/<conversation_id>/classify \
  -H "X-Admin-Api-Key: <ADMIN_API_KEY>"
# -> full classification + routing-flag JSON
```

## 25. Next recommended step

1. Decide whether the WhatsApp Operations Agent should branch on the
   classifier's output (e.g., route straight to escalation on `is_urgent`
   instead of running the happy-path flow) - this is the highest-value
   follow-up and was intentionally left as a decision point, not assumed.
2. Small Admin UI addition: surface `latest_intent`/`latest_sentiment`/
   `latest_urgency` as a badge in the conversations list/detail
   (`apps/admin/components/conversations/`) - the API already returns the
   data.
3. Per `CLAUDE.md` §18, after classifier hardening the roadmap continues to
   "stronger approval/manual takeover", then live WhatsApp readiness - not
   started here.
