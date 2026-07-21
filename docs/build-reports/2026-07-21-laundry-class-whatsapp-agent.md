# Build Report — Laundry Class WhatsApp Agent (KB + LangChain/LangGraph memory + handoff)

**Date:** 2026-07-21

## 1. Build title
Laundry Class WhatsApp AI Agent — file-based knowledge base, LangChain/LangGraph
safe conversation memory, intent routing, human handoff, and end-to-end testing.

## 2. Task objective
Prepare a file-based knowledge base, connect it to the WhatsApp agent, implement safe
conversation memory with LangChain + LangGraph and a persistent checkpointer, add human
handoff for critical cases, and complete the 10 end-to-end test cases plus memory-isolation
and application-restart tests. The agent must answer prices/policies from the KB, collect an
order across several messages, remember earlier details, avoid inventing facts, and escalate
critical cases to a human.

## 3. What was built
A **self-contained `laundry_class/` package** inside `apps/whatsapp-agent/` implementing the
agent as a LangGraph state machine over a LangChain chat model, with a file knowledge base:

- **File KB** (`knowledge_base/laundry_class_knowledge_base.md`, `dummy_orders.json`) —
  prices parsed directly from the markdown so the file is the single source of truth.
- **LangGraph state machine** (`graph.py`) with a **persistent SQLite checkpointer** keyed by
  `thread_id = "whatsapp:<phone>"` — isolated, restart-surviving memory per WhatsApp number.
- **Intent routing** across the 15 required intents (`intents.py`, `flows.py`).
- **Human handoff** with a structured admin notification, emitted once per case (`handoff.py`,
  `observability.py`).
- **Deterministic, mock-first "LLM"** implemented as a real LangChain `BaseChatModel`
  (`responder.py`); a live Anthropic provider is swappable via env but off by default.
- **Masked structured logging** + a team-facing handoff channel (`observability.py`).
- **Runtime** entry point (`runtime.py`), an interactive test console (`scripts/lc_chat.py`),
  and a transcript capture script (`scripts/lc_run_testcases.py`).

## 4. Why it was built
It is the current build-priority module (WhatsApp Operations Agent). Building it as a separate
package keeps the existing rules-based agent and its 95 passing tests untouched (git-safety),
while satisfying the LangChain/LangGraph requirement and the mock-first rules.

## 5. Why prices differ from the task's dummy values
The founder directed us to use the **official Laundry Class prices**
(`laundrykhalas.com/en-ae/personal-laundry/pricing/`) instead of the task's placeholder prices,
and to adapt the test-case expected values to reality. The KB therefore uses real prices
(6kg bag AED 60, two-piece suit dry clean AED 45, shirt wash & press AED 9, evening dress dry
clean AED 100, free pickup & delivery, ~24h turnaround). Policies the website does not publish
(refund, damage, cancellation, stain, delivery windows) remain clearly-labelled testing values.

## 6. Files created
```
apps/whatsapp-agent/knowledge_base/laundry_class_knowledge_base.md
apps/whatsapp-agent/knowledge_base/dummy_orders.json
apps/whatsapp-agent/laundry_class/__init__.py
apps/whatsapp-agent/laundry_class/knowledge_base.py    # load + section split + price parser + order lookup
apps/whatsapp-agent/laundry_class/state.py             # LangGraph ConversationState + reducers
apps/whatsapp-agent/laundry_class/intents.py           # 15-intent classifier
apps/whatsapp-agent/laundry_class/slots.py             # name/area/service/items/time/payment/address
apps/whatsapp-agent/laundry_class/flows.py             # contextual intent resolution, estimation, recall
apps/whatsapp-agent/laundry_class/handoff.py           # handoff decision + admin notification format
apps/whatsapp-agent/laundry_class/responder.py         # LangChain BaseChatModel + reply composition
apps/whatsapp-agent/laundry_class/graph.py             # the LangGraph turn brain + notify node
apps/whatsapp-agent/laundry_class/runtime.py           # InMemory/Persistent runtimes, thread_id
apps/whatsapp-agent/laundry_class/config.py            # mock-first config
apps/whatsapp-agent/laundry_class/observability.py     # masked logs + admin channel
apps/whatsapp-agent/tests/test_laundry_class_agent.py  # 13 e2e tests (10 TCs + isolation + restart)
apps/whatsapp-agent/scripts/lc_chat.py                 # interactive WhatsApp-style console
apps/whatsapp-agent/scripts/lc_run_testcases.py        # transcript capture
apps/whatsapp-agent/whatsapp_agent_test_report.md      # the test report (Part 10)
docs/build-reports/2026-07-21-laundry-class-whatsapp-agent.md
docs/build-reports/2026-07-21-laundry-class-agent-transcripts.txt
docs/architecture/laundry-class-memory-separation.md   # deliverable #14 note
```

## 7. Files modified
- `apps/whatsapp-agent/pyproject.toml` — added langgraph, langchain-core, langgraph-checkpoint-sqlite; package discovery includes `laundry_class*`.
- `apps/whatsapp-agent/.gitignore` — ignore `*.sqlite`, `logs/`, egg-info, venv.
- `docs/00-Home.md`, `docs/weekly-reports/week-01-report.md`, `docs/presentation-notes/` — updated.

## 8. API endpoints added/changed
None. The agent is exposed via `laundry_class.runtime` (library + CLI). Wiring it behind the
existing `/api/test-chat/message` FastAPI route or a WhatsApp webhook is a small, deferred
follow-up (documented in Known limitations).

## 9. Database tables/models added/changed
None in the app DB. LangGraph memory lives in its own SQLite checkpointer file
(`laundry_class_memory.sqlite`), separate from the app's `whatsapp_agent.db`.

## 10. UI pages/components added/changed
None. Testing is via the CLI console and the automated suite.

## 11. Agent behaviour added/changed
New agent (Laundry Class) with: greeting-once discipline, KB-grounded pricing (never invents),
progressive multi-message order collection with running estimate, dummy order reference on
confirm, dummy-order status/recall by phone, delivery reschedule (recorded, never falsely
confirmed), and human handoff for refund/damage/missing-item/payment-dispute/human-request/
special-care/hazardous/threat/anger/3× fallback.

## 12. Integrations added/changed
LangChain (`langchain-core`) and LangGraph (`langgraph`, `langgraph-checkpoint-sqlite`). No
external network calls: the model node is deterministic by default.

## 13. What is mock-only
Everything. Deterministic mock model (no LLM API calls), dummy orders, dummy policies, mock
"admin channel" (a local log file + in-process sink), dummy order references (`LC-TEST-9xxx`).

## 14. What is live
Nothing. No live WhatsApp, Stripe, LLM, or external API. Prices are real reference values but
are read from a static file, not a live pricing API.

## 15. What is intentionally deferred
Live LLM provider (wired but off), live WhatsApp webhook wiring, classifier agent, real order
DB integration, admin UI surface for the handoff queue, cross-turn item de-duplication when a
customer re-describes previously stated items (see Known limitations).

## 16. Tests run
`python -m pytest` (full suite) and `pytest tests/test_laundry_class_agent.py -v`.

## 17. Test results
- **142 passed** across the whole `apps/whatsapp-agent` suite (95 pre-existing + new).
- **13/13** Laundry Class e2e tests pass (TC1–TC10 + memory isolation + restart persistence).
- `ruff check laundry_class/ tests/... scripts/...` — clean.
- Full transcript evidence: `docs/build-reports/2026-07-21-laundry-class-agent-transcripts.txt`.

## 18. Bugs/issues found (and fixed during the build)
- Item regex missed trailing `?` (`"a suit?"`) → broadened terminators.
- `IGNORECASE` name capture grabbed connectors (`"Maya and"`) → connector trimming.
- Mid-order service message dropped out of the flow → order-continuation intent rule.
- `"Yes, confirm."` failed the affirmative match → leading-word match.
- Complaint text (`"a tear"`) polluted order slots → central order-slot gate.
- Reschedule mistook the *current* time for the requested new time → two-step ask.
- Digit-glued `"6kg bag"` not parsed → explicit bag/kg detection.

## 19. Known limitations
- **Item re-description (TC9):** if a customer first says "two dresses" then re-describes them
  ("one normal, one evening gown"), items accumulate rather than replace, so the estimate over-
  counts. The reply is still correctly labelled an **estimate**, and no exact/express price is
  invented — but the item list is imperfect. A real LLM node (already swappable) resolves this.
- No live channel wiring yet (library/CLI only).
- Deterministic model has an accuracy ceiling versus a real LLM on free-form phrasing.

## 20. Security/privacy notes
- Phone numbers are **masked** in application logs (`+97150***01`); the team-facing handoff
  channel keeps the full number because it is operationally required to act on the case.
- No passwords, card numbers, CVV, PIN, OTP, or tokens are ever logged or requested; the payment-
  dispute reply explicitly warns the customer not to share them.
- Memory is strictly isolated per WhatsApp number via `thread_id`; a second number cannot read
  the first's name, address, order, or complaint (verified by TC8).
- State stores no sensitive fields (only name, phone, order slots).

## 21. Cost / LLM usage notes
Zero. The default model is deterministic and makes no API calls. No tokens consumed.

## 22. Screens/pages to demo
Terminal console `python scripts/lc_chat.py --phone +971500000101`, the captured transcript
file, `logs/admin_handoffs.log`, and `logs/laundry_class_agent.log` (masked).

## 23. Commands to run
```
cd apps/whatsapp-agent
./.venv/Scripts/python.exe -m pytest tests/test_laundry_class_agent.py -v
./.venv/Scripts/python.exe scripts/lc_run_testcases.py           # capture transcript
./.venv/Scripts/python.exe scripts/lc_chat.py --phone +971500000101   # interactive
```

## 24. How to verify manually
Run `lc_chat.py`, ask "how much is dry cleaning for a suit?", then "and a shirt?" (memory), then
place an order across several messages, restart the script and ask "what pickup time did I
request?" (persistence), and send "my dress came back torn" (handoff → check
`logs/admin_handoffs.log`).

## 25. Next recommended step
Wire `laundry_class.runtime` behind the existing `/api/test-chat/message` route (or a WhatsApp
webhook) so the admin dashboard console can drive it, and optionally enable the live LLM node in
a staging profile to remove the item-re-description limitation.
