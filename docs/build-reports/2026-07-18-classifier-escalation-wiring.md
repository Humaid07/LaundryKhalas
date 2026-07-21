# Build Report: Operations Agent Reacts to Classifier Flags

## 1. Build title

Wire the WhatsApp Operations Agent to React to Classifier Agent Flags

## 2. Date

2026-07-18

## 3. Task objective

Explicit founder/team follow-up to the Classifier Agent build
(`docs/build-reports/2026-07-18-classifier-agent.md`): couple the two
agents so the WhatsApp Operations Agent no longer attempts its happy-path
order flow on conversations the Classifier Agent has flagged as a
complaint, cancellation, rescheduling, payment issue, B2B lead, or
otherwise urgent/escalated - this was explicitly named as the highest-value
follow-up in that build report's §25 and left as an open decision, not
assumed.

## 4. What was built

- `app/agents/whatsapp_operations/tools.py::requires_escalation(latest_intent,
  latest_urgency)` - policy function: true if urgency/escalation is flagged
  by sentiment, or if the intent is one of 12 intents this agent has no
  tool for (`complaint, pickup_issue, delivery_issue, payment_issue,
  facility_issue, pricing_objection, cancellation, rescheduling, b2b_lead,
  facility_onboarding, driver_support, lost_lead`).
- `app/agents/whatsapp_operations/graph.py`:
  - `AgentState` gained two fields: `latest_intent`, `latest_urgency`.
  - `load_conversation_context` now copies
    `conversation.latest_intent`/`latest_urgency` into state (no new query -
    the row was already being loaded).
  - `decide_next_action` calls `tools.requires_escalation(...)` before
    attempting slot extraction; if true, sets `decision = "escalate"` and
    `error = "classifier_flagged_intent=<intent>"` and returns immediately,
    skipping `extract_order_slots` entirely.
- No change to `safety_filter`, `draft_reply`, `create_approval`, or
  `app/agents/whatsapp_operations/agent.py` - the new escalate path reuses
  the existing escalation machinery unchanged (same code path already used
  for `market_not_configured`, `tool_step_limit_exceeded`, etc.).
- `app/tests/test_classifier_escalation.py` - 4 new tests.
- Documentation: this build report, plus updates to
  `docs/architecture/classifier-agent.md`,
  `docs/decisions/classifier-agent-design-decisions.md`,
  `docs/weekly-reports/week-01-report.md`, `docs/00-Home.md`.

## 5. Why it was built

Explicit founder/team instruction this session, immediately following the
Classifier Agent build. Full rationale for *why* this matters (not just
that it was requested) is in §18 below - a real bug was found and fixed
while implementing this, not just a nice-to-have.

## 6. Files created

- `app/tests/test_classifier_escalation.py`
- `docs/build-reports/2026-07-18-classifier-escalation-wiring.md` (this
  file)

## 7. Files modified

- `app/agents/whatsapp_operations/tools.py`
- `app/agents/whatsapp_operations/graph.py`
- `docs/architecture/classifier-agent.md`
- `docs/decisions/classifier-agent-design-decisions.md`
- `docs/weekly-reports/week-01-report.md`
- `docs/00-Home.md`

## 8. API endpoints added/changed

None. `POST /api/admin/conversations/{id}/run-agent`'s response shape is
unchanged (`decision` can already be `"escalate"` - that value already
existed for other escalation reasons; this just adds a new way to reach
it). No route files touched.

## 9. Database tables/models added/changed

None.

## 10. UI pages/components added/changed

None.

## 11. Agent behavior added/changed

**WhatsApp Operations Agent behavior changed.** Previously it treated every
inbound message identically (attempt slot extraction, then either ask a
follow-up or create an order). Now, if the Classifier Agent flagged the
conversation, it skips straight to escalation - see §4. This is the first
task where the two agents' behavior is coupled; both remain independently
callable (the classifier still always runs on inbound regardless of what
the operations agent later does).

## 12. Integrations added/changed

None.

## 13. What is mock-only

Everything - same mock posture as both agents individually. No live
provider/channel touched.

## 14. What is live

Nothing.

## 15. What is intentionally deferred

- The escalation notice text is still the single generic template
  (`prompts.render_escalation_notice`) regardless of *why* it escalated
  (complaint vs. B2B lead vs. cancellation read very differently to a
  human reviewer, even though the customer-facing text is deliberately the
  same generic "a member of our team will follow up" for safety). The
  *reason* is fully visible to the admin reviewing the approval
  (`HumanApproval.reason`, e.g. `classifier_flagged_intent=complaint`), so
  a human isn't blind to why - but the Admin UI doesn't yet highlight or
  route these differently in the approval queue (e.g. sort urgent ones to
  the top). Not built here.
- No Admin UI change - same gap noted in the classifier build report,
  unchanged by this task.

## 16. Tests run

1. **Full backend test suite** - `docker compose exec -T api pytest
   app/tests -q` - **35 passed, 0 failed** (31 pre-existing + 4 new). No
   existing test needed modification - the two `test_agent_happy_path.py`
   tests that create orders use messages classified as `order_placement`
   (not in the escalate set), so their behavior is unaffected.
2. **Ruff lint** - `docker compose exec -T api ruff check
   app/agents/whatsapp_operations app/tests/test_classifier_escalation.py`
   - all checks passed, no violations.
3. **Live smoke test** against the running dev stack: sent "Please
   reschedule my wash and fold pickup to tomorrow afternoon, Dubai Marina"
   (deliberately containing all three order slots) through
   `POST /api/mock-whatsapp/inbound`, then `POST /api/admin/conversations/
   {id}/run-agent` - result was `{"decision": "escalate", "order_id": null,
   "approval_id": "...", "draft_reply_text": "Hi customer, thanks for your
   patience..."}` - confirmed **no duplicate order was created**.

## 17. Test results

All automated tests pass (35/35). Lint clean. Live smoke test confirmed the
specific bug this task fixes (see §18) no longer reproduces.

## 18. Bugs/issues found

**Found and fixed as part of this task** (not present before this change,
since the classifier's output wasn't consumed by anything yet - this is a
gap this task closes, described here because it's the concrete
justification for the whole task): without this wiring, a message like
*"please reschedule my wash and fold pickup to tomorrow afternoon,
Marina"* contains all three fields `decide_next_action`'s slot extraction
looks for (service_type="wash_and_fold" via "wash and fold", pickup_when=
"tomorrow afternoon", area="Marina") and would have been classified as a
complete, valid new order request - creating a **second, duplicate order**
for a customer who was actually asking to change their existing one, with
no tool anywhere in this agent to recognize the difference. Verified fixed
both by a dedicated regression test
(`test_reschedule_request_escalates_instead_of_duplicate_order`) and live
(§16 item 3).

One implementation pitfall caught and avoided during development (not
shipped, so not a "bug found," but worth recording): the natural first
instinct was to add the escalation check to `load_conversation_context`
(mirroring the existing `manual_takeover` early-return there). That would
have returned from the node *before* `market_id`/`customer_id` were added
to state, and `draft_reply` unconditionally does
`uuid.UUID(state["market_id"])` - which would have raised `KeyError` for
every classifier-triggered escalation. Caught during implementation by
reading `draft_reply`'s code before writing the check, not by a failing
test. Fixed by placing the check in `decide_next_action` instead, which
always runs after `load_conversation_context` has fully populated state.

## 19. Known limitations

See §15. Additionally: the `_ESCALATE_ON_INTENTS` set in
`whatsapp_operations/tools.py` is a manually curated policy list, not
derived automatically from what tools the agent has - if a new tool is
added to the operations agent later (e.g. a real cancellation tool), this
set must be updated by hand or it will keep escalating cancellations
unnecessarily. Documented here so it isn't a silent trap.

## 20. Security/privacy notes

No change. No new PII surface; the escalation reason
(`classifier_flagged_intent=<intent>`) is a label string, not customer
data, and is only visible to admins (same `X-Admin-Api-Key` gate as
everything else).

## 21. Cost/LLM usage notes

None - no additional LLM calls. The classifier's own LLM-gateway call
(already counted in the prior build report) is unchanged; this task adds
no new calls, only a branch on already-computed data.

## 22. Screens/pages to demo

None (backend-only). The effect is visible via the same `/docs`/curl flow
as the classifier build - see §24 below, and
`docs/presentation-notes/week-01-classifier-agent-demo.md` §4 (updated to
reflect that this coupling now exists).

## 23. Commands to run

```
cd "D:\Laundry Khalas App"
docker compose exec -T api pytest app/tests -q
docker compose exec -T api ruff check app/agents/whatsapp_operations
```

## 24. How to verify manually

```
curl -X POST http://localhost:8000/api/mock-whatsapp/inbound \
  -H "Content-Type: application/json" -H "X-Admin-Api-Key: <ADMIN_API_KEY>" \
  -d '{"market_code":"AE","phone_number":"+971500009998","message":"Please reschedule my wash and fold pickup to tomorrow afternoon, Dubai Marina"}'

curl -X POST http://localhost:8000/api/admin/conversations/<conversation_id>/run-agent \
  -H "X-Admin-Api-Key: <ADMIN_API_KEY>"
# -> decision: "escalate", order_id: null (not a duplicate order)
```

## 25. Next recommended step

1. Small Admin UI addition (carried over from the classifier build report,
   now more valuable): surface `latest_intent`/`latest_urgency` and sort/
   highlight escalated approvals in the queue, since there are now
   materially more escalations to review (every complaint/cancellation/B2B
   message routes here instead of silently falling through to a generic
   follow-up question).
2. Consider whether the escalation notice text should vary by reason
   (still generic today, deliberately - see §15) - a founder/team call on
   whether that's worth the added complexity vs. the current safety-first
   uniform message.
3. Per `CLAUDE.md` §18, continue to "stronger approval/manual takeover"
   next unless redirected again.
