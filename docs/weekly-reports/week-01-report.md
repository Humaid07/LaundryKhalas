# Week 1 Report

Covers the period ending 2026-07-18. First weekly report under the
documentation ADR (`docs/decisions/ADR-project-documentation-and-memory-
rule.md`, in force from 2026-07-18) — earlier work in this period is
summarized retroactively from existing audits/decisions/architecture docs.

> **Update (2026-07-20) — WhatsApp agent: humanized + stateful orders.** The
> standalone WhatsApp agent was made humanized and stateful. The chat UI now
> shows a WhatsApp-style **typing indicator** (configurable 2–3s) before
> replies, and — the headline change per founder direction — **the
> conversation now updates a real, queryable order state behind the scenes**.
> A new `Order` model + `services/order_store.py` implement a full mock order
> lifecycle (`draft → active → … → completed/cancelled`, plus cancellation and
> pickup-change requests); a deterministic `order_flow` reads and mutates
> orders for **book / track / cancel / change pickup / add items**; dummy
> orders **LK-AE-1024..1027** are seeded; and an **order/dashboard API**
> (`/api/orders/active|completed|metrics|{id}|complete|status`) exposes it.
> Booking now collects service → items → area → time → confirm and creates an
> **active** order; track returns real status and refuses unknown IDs; cancel
> never auto-cancels. **129 backend tests pass** (+34), typecheck + lint clean,
> live startup verified. Mock-only; dashboard UI wiring is the next step. See
> `docs/build-reports/2026-07-20-whatsapp-agent-stateful-orders.md`.

## 1. Executive summary

The WhatsApp Operations Agent backend and its Admin UI testing console both
exist and work end-to-end in mock mode: a simulated inbound WhatsApp
message can be turned into an agent draft reply, approved by a human, and
turned into a mock order with a mock facility assignment — all logged. This
week's work also stood up the project's documentation system itself (the
ADR requiring build/weekly/presentation reports going forward) and produced
the first build report and demo notes for the Admin UI specifically.

**Later the same week**, the founder/team redirected priorities: a second,
fully independent Standalone WhatsApp Agent (`apps/whatsapp-agent/` +
`apps/whatsapp-chat/`) was built, domain-guarded to laundry/cleaning/
LaundryKhalas topics only, with its own WhatsApp-Web-style chat UI —
ahead of the classifier agent, per `docs/decisions/
ADR-standalone-whatsapp-agent-first.md`. 28 backend tests pass, both
frontends typecheck/lint/build cleanly, and the full required demo flow
(pickup request → clarifying questions → out-of-domain refusal → pricing
from config → prompt-injection refusal) was verified live.

**Then, still this week**, the founder/team explicitly asked to resume the
main roadmap at build priority #3: the Classifier Agent. Built in the main
system (`app/agents/classifier/`), it labels every inbound message with
intent (18 categories), sentiment (5 categories + score), and the routing
flags CLAUDE.md §9 calls for (urgency, complaint, angry, escalation,
refund/cancellation, B2B), runs automatically ahead of the WhatsApp
Operations Agent, and is fully audited. 31 backend tests pass (22
pre-existing + 9 new), lint clean, verified live against the running stack
— see `docs/build-reports/2026-07-18-classifier-agent.md`.

**Same day, immediate follow-up**: the founder/team asked to wire the two
agents together. The WhatsApp Operations Agent now escalates to a human
instead of running its happy-path order flow whenever the Classifier Agent
flags a message as a complaint, cancellation, rescheduling, payment issue,
B2B lead, or otherwise urgent/angry. This closed a real bug found during
implementation: a rescheduling message containing all three order slots
(service/area/time) would otherwise have created a **duplicate order**
instead of being recognized as a change request. 35 backend tests pass (31
+ 4 new), verified live — see `docs/build-reports/
2026-07-18-classifier-escalation-wiring.md`.

## 2. What shipped this week

- FastAPI backend: WhatsApp Operations Agent (LangGraph-orchestrated),
  mock WhatsApp adapter, mock LLM provider, conversation/message/order/
  approval/AI-action-log models and routes, seeded mock market/facility/
  pricing data.
- Next.js Admin UI (`apps/admin/`): 8 routes covering Overview,
  Conversations, Approval Queue, Orders, AI Action Logs, and a Mock
  WhatsApp Test Console — see `docs/build-reports/2026-07-18-admin-ui-
  build.md` for full detail.
- Docker Compose stack running Postgres, Redis, the API, Celery
  worker/beat, and the admin frontend together.
- Documentation system: `CLAUDE.md` rulebook, `docs/00-Home.md` Obsidian
  entry point, architecture/decision/checklist/audit docs, and (new this
  week) the ADR mandating build/weekly/presentation reports for every major
  task going forward.
- Standalone WhatsApp Agent (`apps/whatsapp-agent/` backend on port 8100,
  `apps/whatsapp-chat/` frontend on port 3100): two-layer domain guard
  (keyword filter + system prompt), real (not stubbed) Anthropic/OpenAI
  provider implementations gated behind env-configured keys, official Meta
  WhatsApp Cloud API structure (webhook verify, signature check, send)
  gated behind `WHATSAPP_MODE=live`, and a WhatsApp-Web-style chat UI —
  see `docs/build-reports/2026-07-18-standalone-whatsapp-agent.md`.
- Classifier Agent (`app/agents/classifier/`, main system): deterministic
  18-intent/5-sentiment classifier, routing-flag derivation, the real
  Section D.4 LLM prompt (written, not yet live), auto-run on every inbound
  message plus a manual `POST /api/admin/conversations/{id}/classify` —
  see `docs/build-reports/2026-07-18-classifier-agent.md`.
- Operations Agent ↔ Classifier Agent wiring: the Operations Agent now
  escalates instead of attempting the happy-path order flow when the
  Classifier Agent flagged the conversation - see `docs/build-reports/
  2026-07-18-classifier-escalation-wiring.md`.
- **(2026-07-20) Internal Dashboard structure** (`apps/admin`): a premium
  rose/white **Command Center** with full dark mode and all eight sections
  (Overview, Operations, Sales, SEO Agents, Marketing, Finance, Reports,
  Settings) on LaundryKhalas-specific mock data — a reusable component
  library, Recharts charts, responsive down to mobile (tables → cards).
  Typecheck + production build pass; browser-verified with 0 console errors
  across all pages in light/dark/mobile. Mock-only, no live APIs, no secrets
  — see `docs/build-reports/2026-07-20-internal-dashboard-structure.md`.
- **(2026-07-20) Environment unblocked**: Python 3.12 installed; the
  standalone WhatsApp Agent backend (`apps/whatsapp-agent`, :8100) now runs
  end-to-end on SQLite (95/95 real tests pass; 1 Windows-only test-teardown
  quirk noted).
- **(2026-07-21) Operations expanded to four surfaces** (`apps/admin`,
  `/operations`): added two new **top-level** tabs — **Drivers** (pickup/
  delivery fleet: 10 KPIs, driver overview, pickup/delivery queues with
  area-only privacy, performance, issues) and **Customer Charges / Payments**
  (operational customer-level payment view distinct from Finance: 10 KPIs,
  payment overview, pending payments, refund requests, adjustments, payment
  issues, B2B invoices; mock-only, Stripe off, refunds/adjustments require human
  approval, no card/CVV/bank data). Existing Customer Facing & Facility Facing
  untouched. Typecheck + build + lint clean; browser-verified light/dark/mobile
  (no horizontal overflow). Mock-only — see `docs/build-reports/
  2026-07-21-operations-drivers-payments-sections.md`.

## 3. What changed since last update

N/A — this is the first weekly report.

## 4. Screens/features ready to demo

All 8 Admin UI routes, live-verified today: Overview, Mock WhatsApp Test
Console, Conversations inbox + detail, Approval Queue, Orders list +
detail, AI Action Logs. See demo script in `docs/presentation-notes/
week-01-admin-ui-demo-notes.md`.

Also ready: the Standalone WhatsApp Agent's `/chat` (WhatsApp-Web-style
console) and `/settings` pages at `http://localhost:3100` - see
`docs/presentation-notes/week-01-standalone-whatsapp-agent-demo.md` for
the suggested demo flow.

The Classifier Agent is backend/API-only (no dedicated UI page yet) - demo
via the existing AI Action Logs page (`/admin/ai-logs`, filter for
`agent_name: classifier_agent`), `/docs`, or curl, per `docs/
presentation-notes/week-01-classifier-agent-demo.md`; its output
(`latest_intent`/`latest_sentiment`/`latest_urgency`) is already visible in
raw API responses from the existing Admin UI's conversation endpoints, just
not rendered as a badge/filter yet. Its effect on the Operations Agent
(escalating instead of creating an order) is visible today via the Orders
and Approval Queue pages - a flagged conversation produces an approval with
`action_type: escalate_to_human` and no order, instead of the usual order
confirmation.

## 5. Backend progress

Stable. Re-verified today: `/health`, all `/api/admin/*` list/detail
endpoints, and the full inbound-message → agent-run → approval → order
flow, all returning correct, non-invented data (seeded facility/pricing).

## 6. Frontend progress

All 8 planned Admin UI routes exist and render (HTTP 200) against live
backend data. No automated frontend test suite yet, but `npm run
typecheck` / `lint` / `build` were run today (via the built Docker image,
since the host shell has no Node) and all passed — typecheck clean, lint
has 1 non-blocking warning, production build compiles all 10 routes. See
build report §16/§17.

The new Standalone WhatsApp Agent's frontend (`apps/whatsapp-chat/`, 3
routes: `/`, `/chat`, `/settings`) also passed typecheck/lint/build
cleanly (0 lint warnings) on the first successful attempt.

## 7. Agent progress

The main WhatsApp Operations Agent's happy-path behavior (ask for missing
service/area/time, price from config, create mock order, assign mock
facility, draft reply, queue for approval) is unchanged for messages the
classifier doesn't flag - re-verified working today via the Admin UI's
underlying API. **What did change**: it now escalates instead of running
that flow when the Classifier Agent flagged the conversation - see below.

New this week: the Standalone WhatsApp Agent (separate codebase, see §2)
— domain-guarded, slot-filling, config-sourced pricing, never invents
data, refuses prompt injection. Not a classifier and not intended to
become one - see `docs/architecture/domain-guard.md`.

Also new: the Classifier Agent (main system) — runs automatically on every
inbound message ahead of the Operations Agent, per CLAUDE.md §9. **As of
the same-day follow-up (see executive summary), the Operations Agent now
consumes the classifier's output**: `decide_next_action` checks
`Conversation.latest_intent`/`latest_urgency` and escalates instead of
attempting slot extraction when flagged - see `docs/architecture/
classifier-agent.md` "How the Operations Agent reacts to it".

## 8. Database progress

No schema changes this week. Three new read-only routes were added
exposing existing tables (`OrderEvent`, `AIActionLog` by `order_id`,
`Market`) — no migrations required.

## 9. Security/privacy progress

`X-Admin-Api-Key` required on all admin routes (still a shared placeholder
key, not per-user auth — tracked in `docs/checklists/live-whatsapp-
readiness.md`). CORS locked to an explicit two-origin localhost allow-list,
not a wildcard. No secrets found committed on inspection of `.env`/
`.env.example`.

## 10. Testing progress

- Backend: full agent flow (inbound → run-agent → approve → order created)
  and all 5 admin list/read endpoints verified live today, all passing.
  Manual takeover / release-takeover / manual-reply also verified: agent
  correctly refuses to run (HTTP 409) while takeover is active, manual
  replies bypass the approval queue by design, release restores normal
  agent-run capability.
- Frontend: HTTP-level route smoke test (all 8 routes → 200) plus
  `npm run typecheck` / `lint` / `build`, all run today via the built
  Docker image (host shell has no Node, but the image does) — typecheck
  clean, lint 1 non-blocking warning, production build compiles cleanly.
  No automated unit/integration/e2e test suite exists yet.
- One transient bug found and fixed during today's verification: a stale
  Next.js dev cache caused both dynamic detail pages
  (`/admin/conversations/[id]`, `/admin/orders/[id]`) to 500 on first load;
  a container restart resolved it (root cause: stale Docker volume cache,
  not a code defect — full detail in the build report §18). Separately, a
  production-build attempt against the *running* container's shared
  `.next` volume failed for the same class of reason (volume busy/
  conflicting with `next dev`); building from a fresh container off the
  already-built image avoided it entirely (build report §16 item 5).
- Classifier Agent: 9 new backend tests, all passing (31/31 full suite),
  ruff lint clean. One test-fixture collision found and fixed (new test
  file reused phone numbers already claimed by `test_approval_flow.py`,
  causing a shared-conversation false failure - renumbered, not a product
  bug) and one lint violation found and fixed (unused variable, resolved by
  putting it to use in the audit log instead of discarding it) - see build
  report §16.
- Operations Agent ↔ Classifier Agent wiring: 4 new backend tests, all
  passing (35/35 full suite), ruff lint clean. Live-verified specifically
  against the duplicate-order bug this task fixes (see build report §18)
  - confirmed a reschedule message with all three order slots present now
  escalates with `order_id: null` instead of creating a duplicate order.

## 11. Blockers

None blocking. The Node.js tooling gap on this session's host shell was
worked around by running `npm` commands inside Docker instead (the image
already has Node installed), so typecheck/lint/build verification is now
complete.

## 12. Risks

- No automated frontend tests — regressions in the UI would currently only
  be caught by manual click-through or the typecheck/lint/build checks run
  today.
- Single shared admin API key — acceptable for internal testing only.
- Missing customer-name/phone resolution endpoint means conversation/order
  detail views show a raw customer ID rather than a name — a real usability
  gap for staff, tracked but not yet scheduled.
- `.env` contains an unused `EVOLUTION_API_KEY`/`EVOLUTION_API_BASE_URL`
  pair referencing an unofficial WhatsApp automation tool banned by
  `CLAUDE.md` §4. Confirmed unused in code and not committed to git, so
  low risk today, but it's unexplained dead config worth a decision.
- This repository is not currently under git version control at all —
  no version history, no rollback safety net, and `CLAUDE.md` §15's
  git-safety rules can't be followed until this is set up.

## 13. Decisions needed from founder/team

- Confirm whether closing the customer-detail/name-resolution gap (§3 of
  `docs/audits/admin-ui-start-report.md`) should be prioritized before or
  after the Classifier Agent, since it's a UI usability gap rather than a
  roadmap-blocking one.
- Should the unused Evolution API credential in `.env` be removed, or is
  there a reason it's there that should be documented instead?
- Should this repository be initialized under git now, before further work
  accumulates without version history?
- No other open decisions this week beyond the two already flagged in
  `docs/audits/prototype-md-review.md` (market scope, reporting cadence
  day) — still outstanding from before this week.
- Which of the two Meta WhatsApp Cloud API integration points (main
  system's stub, or the standalone agent's working implementation)
  becomes the real production integration, so neither ends up pointed at
  the same live phone number by accident.
- Whether the Standalone WhatsApp Agent stays a permanently separate tool
  or gets folded into the main system later - not decided in this build.
- ~~Whether the WhatsApp Operations Agent should be wired to react to the
  Classifier Agent's output~~ - **decided and built same day**: yes, see
  executive summary and `docs/build-reports/
  2026-07-18-classifier-escalation-wiring.md`.
- New: whether the generic escalation notice text should vary by reason
  (complaint vs. B2B lead vs. cancellation) now that materially more
  conversations route through escalation - currently deliberately uniform
  for safety (build report §15/§25).

## 14. Deviations from roadmap/spec

One, explicit and founder/team-directed: `CLAUDE.md` §18's stated order
(WhatsApp Agent → Admin UI → Classifier Agent → ...) was interrupted after
Admin UI to build the Standalone WhatsApp Agent instead, ahead of the
Classifier Agent - documented as a deliberate, temporary reordering in
`docs/decisions/ADR-standalone-whatsapp-agent-first.md`, not a silent
drift. A request to also wire in an unofficial WhatsApp automation tool
(Evolution API) as part of that build was raised and explicitly declined
this week - see §12 and the ADR - no unofficial automation was added. The
roadmap then resumed at the Classifier Agent (build priority #3) per
explicit founder/team instruction later the same week - back in sequence
with `CLAUDE.md` §18 as of this report.

## Addendum (2026-07-21) — Laundry Class WhatsApp Agent: KB + LangChain/LangGraph memory + handoff

A dedicated, self-contained **Laundry Class** WhatsApp agent was built in
`apps/whatsapp-agent/laundry_class/` (separate from the existing rules-based agent,
so its 95 tests stay green). What shipped:

- **File knowledge base** (`knowledge_base/laundry_class_knowledge_base.md`,
  `dummy_orders.json`) using the **official Laundry Class prices** (founder directive:
  real prices over the task's placeholders, tests adapted). Prices are parsed from the
  markdown so the file is the single source of truth.
- **LangChain + LangGraph** implementation with a **persistent SQLite checkpointer**
  keyed by `thread_id = whatsapp:<phone>` → isolated, restart-surviving memory per
  number. Model node is a deterministic LangChain `BaseChatModel` (mock-first, no LLM
  calls); a live Anthropic node is swappable but off.
- **Intent routing** (15 intents), progressive **order collection**, dummy-order
  **status/recall**, **delivery reschedule** (recorded, never falsely confirmed), and
  a **human-handoff** workflow with a structured, once-per-case admin notification.
- **Masked logging** + a team handoff channel; no card/CVV/PIN/OTP ever logged or asked.

**Testing:** 13/13 Laundry Class e2e tests pass (TC1–TC10 + memory isolation + restart);
full repo suite **142 passed**; ruff clean. Evidence: `whatsapp_agent_test_report.md`,
`docs/build-reports/2026-07-21-laundry-class-agent-transcripts.txt`, `logs/`.
**Known limitation:** TC9 item re-description over-counts the estimate (still labelled an
estimate, no invented price); resolved by enabling the swappable live-LLM node. Details:
[[2026-07-21-laundry-class-whatsapp-agent]] and [[laundry-class-memory-separation]].

## 15. Next week's plan

1. Human browser walkthrough of `docs/checklists/admin-ui-manual-test-
   script.md` and `docs/checklists/standalone-whatsapp-agent-test-
   script.md` to catch anything HTTP status/typecheck/lint/build checks
   can't (visual layout, console errors, click targets) — the one
   verification step not yet completed in any session, for either UI.
2. Founder/team decision on the risk items in §12, plus the new
   two-Meta-integrations question in `docs/checklists/
   live-whatsapp-readiness.md` (this system now has two independent,
   unreconciled Meta WhatsApp Cloud API code paths - the main system's
   stub and the standalone agent's working implementation).
3. Small Admin UI addition: surface `latest_intent`/`latest_urgency` as a
   badge and sort/highlight escalated items in the Approval Queue - more
   valuable now that classifier-driven escalations are a regular
   occurrence, not just a hypothetical (flagged in both classifier build
   reports' §25).
4. Per `CLAUDE.md` §18, continue to "stronger approval/manual takeover"
   next unless redirected again.
