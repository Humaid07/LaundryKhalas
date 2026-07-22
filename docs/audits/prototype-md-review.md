# Prototype Markdown Review

Review of all Markdown documentation in the old prototype at
`D:\LaundryKhalas\LaundryKhalasPrototype`, performed to extract useful
product/technical context before continuing new work in this repository.
Per `CLAUDE.md` §3, the prototype is reference material only — this
review does not change the new project's source of truth, and nothing
described below has been copied into code.

**Method**: three parallel research passes covered (a) the prototype's own
`CLAUDE.md` + core project/architecture/decision/database/roadmap docs,
(b) the large `docs/specs/` bundle (master build spec, agentic-OS spec,
marketing/SEO spec), and (c) agent/security/checklist/audit/Q&A docs. Every
file below was read in full (or, for the two largest spec files, read in
sections) and compared against this repo's `CLAUDE.md`.

## 1. Markdown files found

92 Markdown files, all under `D:\LaundryKhalas\LaundryKhalasPrototype`
(excluding `node_modules`, `.next`, `.git`, and the pytest cache stub).

**Root**
- `CLAUDE.md` — the prototype's own rulebook (superseded by this repo's `CLAUDE.md`)
- `backend/README.md`, `backend/DELIVERY_NOTES.md` (the latter self-marked "Superseded" in its own header)

**`docs/` top level**
- `00-Home.md`, `01-Project-Overview.md`, `02-90-Day-Roadmap.md`,
  `03-Current-Build-Status.md`, `04-Open-Questions.md`, `05-Glossary.md`,
  `README.md`

**`docs/agents/`** — `Agent-Tool-Permissions.md`, `Approval-Gated-Actions.md`,
`Classifier-D4.md`, `In-App-Command-Agent.md`, `Marketing-Agents.md`,
`Operations-Agent.md`, `SEO-Agents.md`

**`docs/architecture/`** — `Agent-Architecture.md`, `Approval-Queue.md`,
`Backend-Architecture.md`, `Channel-Architecture.md`,
`Frontend-Architecture.md`, `LLM-Gateway.md`, `Market-Configuration.md`,
`System-Architecture.md`, `whatsapp-agent-mvp-architecture.md`

**`docs/audits/`** — `current-prototype-reconciliation-report.md` (~25KB),
`week-1-gap-audit.md` (~23KB), `week-1-whatsapp-dashboard-start-report.md` (~12KB)

**`docs/checklists/`** — `admin-dashboard-mvp-checklist.md`,
`launch-readiness-checklist.md`, `live-integration-approval-checklist.md`,
`live-readiness-checklist.md`, `pre-coding-checklist.md`,
`security-privacy-compliance-checklist.md` (~17KB), `week-1-reconciliation-checklist.md`

**`docs/database/`** — `AIActionLog.md`, `Core-Tables.md`, `CostTracking.md`,
`Database-Overview.md`, `HumanApproval.md`, `Order-State-Machine.md`, `RLS-and-RBAC.md`

**`docs/decisions/`** — `ADR-001-market-scope.md` through `ADR-006-security-before-live.md`,
`current-build-decisions.md`

**`docs/maps/`** — 7 tiny MOC (Map of Content) index files

**`docs/meetings/`** — `README.md`, `template-meeting-notes.md`

**`docs/prompts/`** — `claude-prompts.md`, `dev-handoff-prompts.md`, `gamma-prompts.md`

**`docs/q-and-a/`** — `Board-QA.md`, `Founder-QA.md`, `Security-QA.md`, `Technical-QA.md`

**`docs/roadmap/`** — `Month-1-Foundation.md`, `Month-2-Live-Supervised-Operations.md`,
`Month-3-Scale-and-Production.md`, `Week-1-Reconcile-Scaffold.md` through
`Week-12-Phase-0-Exit.md` (12 weekly files)

**`docs/security/`** — `Authentication-and-Authorization.md`, `Consent-and-Privacy.md`,
`CSP-and-Browser-Security.md`, `LLM-Security.md`, `Load-Testing-and-Performance.md`,
`Payment-Security.md`, `Secrets-Management.md`, `Security-Overview.md`,
`Token-Security.md`, `Webhook-Security.md`

**`docs/specs/`** — `00-master-build-spec.md` (~155KB, the single largest
and most authoritative old spec), `01-agentic-os-spec-full.md` (~61KB —
**note**: despite its README describing it as an "operations detail"
companion to the master spec, its actual content is a full, unsplit copy
of the Marketing & SEO Agentic OS spec, word-for-word identical to the
`02-marketing-seo-agentic-os/` bundle below — a labeling inconsistency in
the prototype itself, not a second independent spec), `02-marketing-seo-agentic-os.md`
plus its `02-marketing-seo-agentic-os/` subfolder (7 files: `00-platform.md`,
`01-agent-formula.md`, `02-agents-seo.md`, `03-agents-marketing.md`,
`05-publishing.md`, `06-reporting-and-metrics.md`, `07-build-sequence.md`,
`README.md`), `03-roadmap-90-day.md` (~14KB), `04-project-understanding.md` (~8KB), `README.md`

**Skipped**: `backend/.pytest_cache/README.md` (tool boilerplate, not
project content) and `docs/templates/*.md` (4 empty templates, no content
to extract).

## 2. Useful product context

- **Business model**: asset-light global cleaning/laundry marketplace —
  the platform owns no facilities and employs no drivers, coordinates
  third-party facilities (who use their own drivers) invisibly to the
  customer. Revenue is a 20–45% margin on transactions via Stripe (B2C) or
  invoicing (B2B), varying by fulfilment model (`01-Project-Overview.md`,
  `00-master-build-spec.md` §B.1.1, §B.3).
- **Strategic thesis**: the agent system is meant to let ~4–5-person
  regional teams run 100+ country markets — agents do the operational
  coordination (intake, dispute triage, lead qualification, marketing
  content, internal ops commands), humans are exception-handlers and
  strategists, not day-to-day operators (`01-Project-Overview.md`,
  `System-Architecture.md`, `00-master-build-spec.md` §B.1.2–B.1.3).
- **Three-agent-system product shape**: System 1 is the customer-facing
  Operations Agent (internally named "Zoya" in the master spec), System 2
  is a staff-facing in-app AI command layer with role-specific overlays
  (customer/driver/facility/admin), System 3 is an async Conversation
  Intelligence Classifier. A separate Marketing & SEO Agentic OS module
  (~14 SEO agents + 9 marketing agents) sits alongside these three
  (`Agent-Architecture.md`, `00-master-build-spec.md` §B.5, §B.7).
- **Verified Delivery Protocol (VDP)**: a 4-step proof-of-handoff flow at
  pickup/delivery — geofence entry → arrival checklist → photo/GPS/OTP/
  micro-rating → validation — enforcing "No Data, No Movement" at the DB
  level. Paired with two scoring systems: Facility PPI (Performance Index,
  0–100, 5 tiers controlling order-allocation volume) and a Driver Score
  (0–100) (`05-Glossary.md`, `00-master-build-spec.md` §B.6).
- **Operating principle, stated crisply**: "Agents research, draft,
  monitor, and recommend. Humans approve, send, pay, register, and own
  canonical data and facts." (`docs/agents/Approval-Gated-Actions.md`) —
  a cleaner one-line phrasing of what this repo's `CLAUDE.md` §6 says at
  length; worth keeping as a mental shorthand.
- **Approval-queue staffing model**: any team member can clear the queue,
  so operational work is never blocked on a single person
  (`Approval-Gated-Actions.md`, security checklist item 19).
- **Repo privacy stance**: the old repo was explicitly kept private
  because it contains business/market strategy (`docs/q-and-a/Security-QA.md`)
  — a reasonable default assumption for this repo too.
- **Weekly Friday written update, no exceptions** was a standing founder
  cadence rule (`docs/meetings/README.md`) — not currently reflected in
  this repo's `CLAUDE.md` weekly-report rule (which doesn't pin a day);
  worth confirming with the founder/team if that cadence still applies.
- **Three fulfilment models** (`00-master-build-spec.md` §B.3): Model 1,
  facility-employed drivers (default, ~20% margin); Model 2,
  platform-freelance drivers (~15%, legally gated per market); Model 3,
  platform-owned fleet (~25%+). Relevant background for whenever the
  driver/VDP module (build-order item 7) starts.

## 3. Useful technical context

- **Order state machine**: a 24-state canonical path enforced by a
  Postgres `BEFORE UPDATE` trigger that rejects invalid transitions at the
  database layer, not just in application code (`Order-State-Machine.md`,
  `backend/DELIVERY_NOTES.md`). A strong "no data, no movement" pattern
  worth reusing when the order/driver flow is built out further.
- **Authority matrix (A/H/M)**: every agent tool/action is classified
  Autonomous / Human-only / Mixed and — per the more detailed
  `Agent-Tool-Permissions.md` — enforced at the **tool-gating layer**
  (the agent literally cannot call a Human-only tool), not just via a
  prompt instruction. A 38-beat version of this matrix exists in
  `00-master-build-spec.md` §B.8. More concrete and enforceable than a
  prose list of "risky actions."
- **Role × tool permission matrix**: an explicit table of
  Customer/Driver/Facility/Admin × (place order / check status / update
  status / override / file complaint) — a reusable template for scoping
  WhatsApp Agent and admin-role permissions (`Agent-Tool-Permissions.md`).
- **Approval-gated reply pattern, actually implemented and working**: the
  booking agent drafts a reply → calls `create_approval_request` → only
  the approval-approve handler sends via the channel adapter; reject never
  sends; manual takeover suppresses agent drafting entirely
  (`week-1-whatsapp-dashboard-start-report.md` §4, `backend/README.md`).
  This is close to a proven reference implementation of this repo's own
  "every reply needs approval" rule.
- **`ChannelAdapter` interface pattern**: a base class with
  `receive_inbound_message`/`send_message`, a fully-implemented
  `MockWhatsAppAdapter` (zero external calls), and a
  `MetaCloudWhatsAppAdapter` **stub that raises on instantiation** so it
  can never be accidentally selected — enforces mock-first at the type
  level, stronger than a config flag alone (`whatsapp-agent-mvp-architecture.md`,
  `Channel-Architecture.md`, `week-1-whatsapp-dashboard-start-report.md` §4).
- **AIActionLog + CostTracking schema shape**: an immutable per-call audit
  log (tokens, cost, latency, model, model_tier, status) plus a
  per-conversation cost rollup, with a 5-layer cost-ceiling design
  (per-message, per-conversation, per-customer-daily, global-daily,
  anomaly detection) enforced via Redis atomic counters
  (`AIActionLog.md`, `CostTracking.md`, `LLM-Gateway.md`,
  `security/LLM-Security.md`). Directly matches this repo's rules 10/11
  (log every agent/tool action).
- **Market Config concept**: one config row per market carrying country
  code, city, language, pricing, service areas, fulfilment model,
  publishing adapter, WhatsApp number, cost ceilings, and a
  `regulatory_compliance_flag` gate — "new market = config row, not
  code" (`Market-Configuration.md`). Good future-proofing pattern for
  eventual multi-market work (currently out of scope).
- **RLS/RBAC target shape**: object-level + market-scoped Postgres row
  security policies (driver sees only assigned orders, facility sees own
  orders, admin sees own market) (`RLS-and-RBAC.md`) — a reasonable target
  design for later, though the old prototype itself never actually
  enforced this (see §4).
- **Classifier taxonomy** (`docs/agents/Classifier-D4.md`,
  `00-master-build-spec.md` §D.4): 18 intent categories, 5-category
  sentiment (happy/neutral/frustrated/urgent/angry) plus a numeric -1..+1
  score, a sales-stage delta, topic label, and routing rules
  (`is_urgent`, `is_escalated`, `needs_followup` thresholds) with a
  verbatim example prompt, designed as a cheap Haiku-tier async call
  (~$0.0001/message, 2–3s turnaround). A strong concrete starting point
  for this repo's build-priority-#3 Classifier Agent when it's actually
  started.
- **Marketing/SEO agent-formula design** (`02-marketing-seo-agentic-os/`,
  duplicated in `01-agentic-os-spec-full.md`): a declarative per-agent
  spec template (ID/Domain/Disposition/Trigger/Inputs/Logic/Output
  Contract/Destination/Connectors/Human Gate/Frequency/Success
  Criterion/Failure Handling/Dependencies), 5 disposition tags
  (Full/Draft/Monitor/Advisory/Assist) signaling autonomy level per agent,
  a "dedup gate" requiring unique+general+local+reviews+FAQ content before
  an area/landing page can reach the approval queue, and a "verified
  facts" rule (facts come only from human-curated config, never invented
  by an agent). The most fleshed-out reusable design in the whole
  prototype, and still on this repo's own roadmap (build-order item 9).
- **In-App Command Agent concept** (`docs/agents/In-App-Command-Agent.md`):
  a staff-facing natural-language assistant with broad tool access gated
  by typed-"confirm" prompts on high-risk actions — a "System 2" idea not
  currently in this repo's `CLAUDE.md` at all; worth keeping in mind for
  later.
- **Privacy firewall system-prompt discipline** (`00-master-build-spec.md`
  §D.2): concrete rules like "never share phone/email/full address with
  facility or driver," "never quote a price not returned by a tool call,"
  "never admit fault," and identity-stability instructions under
  prompt-injection pressure — directly useful for hardening the WhatsApp
  Operations Agent's system prompt.
- **`security-privacy-compliance-checklist.md`'s tiered structure**:
  24 numbered sections (auth, RBAC, tokens, consent, privacy policy, AI
  disclosure, SQL injection, secrets, key rotation, CSP, connection
  pooling, caching, load testing, LLM gateway security, PII masking,
  audit logging, approval gates, webhooks, payments, logging, monitoring,
  dependency scanning) organized into REQUIRED BEFORE CODING / BEFORE
  WEEK 2 / BEFORE LIVE PILOT / BEFORE PRODUCTION / LATER HARDENING tiers —
  the single most reusable artifact found in the whole review, and this
  repo currently has no equivalent checklist at all.
- **`live-integration-approval-checklist.md`**: a per-integration
  mock-to-live sign-off template (env var identified, webhook signature
  verification in place, failure/fallback behavior defined, market scope
  confirmed, rollback plan) — maps directly onto this repo's "no live X
  unless explicitly approved" rules and could become the concrete
  mechanism for granting that approval.

## 4. Outdated assumptions

- The entire prototype roadmap (Weeks 1–12, Months 1–3, the "90-day" spec
  dated for "July–September 2026") reflects a different build order and
  calendar than this repo's staged priority list. No date or week number
  from the prototype should be treated as current.
- **Market scope is inconsistent even within the old docs**: the master
  spec and roadmap describe "UAE + Qatar live," `ADR-001-market-scope.md`
  reportedly narrowed this to "UAE live, Qatar future," and
  `pre-coding-checklist.md`/`Board-QA.md` describe Abu Dhabi + Dubai live
  with Doha TBD. This repo's `CLAUDE.md` doesn't mention Qatar at all —
  market scope should be treated as fully open/TBD, not inherited from
  any of these conflicting old statements.
- **Hosting/infra is stale and points a different direction entirely**:
  Railway (backend) + Vercel (frontend), with an unresolved "cutover to
  Hetzner + Docker" debate, plus AWS S3/DigitalOcean Spaces, DigitalOcean
  Kubernetes, GitHub Actions, Sentry, Metabase/Looker
  (`03-roadmap-90-day.md`, `00-master-build-spec.md` §B.9.5). This repo's
  `CLAUDE.md` instead specifies a Cloudflare-first direction (Pages/
  Workers/R2/AI Gateway) as a later-phase target — none of the old infra
  list should be treated as current guidance.
- **LangGraph was spec-locked but never actually adopted** in the old
  prototype — the booking agent was hand-rolled sequential Python,
  repeatedly flagged internally as needing a "REBUILD" onto LangGraph
  (`Operations-Agent.md`, both audit reports). This repo's `CLAUDE.md`
  mandates LangGraph from the start, so only the old agent's tool
  list/behavior is worth referencing, not its orchestration code.
  Likewise the old `LLMService.complete()` had no `tools` parameter —
  tool orchestration lived outside the gateway in hand-rolled code
  (`current-prototype-reconciliation-report.md` §11) — a gap this repo's
  `llm_service` should design around from day one, not repeat.
- **Test counts and "current status" tables are stale, self-contradictory
  snapshots** of the old codebase (15/19/49/85 differing test-count claims
  across `backend/README.md`, `backend/DELIVERY_NOTES.md`, and the
  audits) — `DELIVERY_NOTES.md` is explicitly marked "Superseded" in its
  own header. None of this describes anything that exists in this repo.
- Classifier, marketing/SEO agents, and driver/customer apps were being
  actively built or scheduled for Month 1–3 in the old prototype; all of
  these are explicitly deferred modules in this repo right now.
- The old frontend was Next.js with in-memory mock data
  (`lib/mock-data.ts`, an `AppProvider` React context) and only 1 of
  roughly 15 pages actually called the backend — not representative of
  this repo's admin UI, which is fully backend-wired.

## 5. Conflicts with current architecture (this repo's `CLAUDE.md`)

- **WhatsApp provider — direct conflict.** The prototype's architecture
  docs and roadmap repeatedly name **Respond.io** as the WhatsApp channel
  adapter target (`Channel-Architecture.md`, `Week-3`/`Week-6` roadmap
  docs, `00-master-build-spec.md` §B.5.12/§B.9.4/§D.2, and even
  `security/Webhook-Security.md`/`Payment-Security.md` in passing), with
  "Wati" mentioned as an alternative in the marketing/SEO spec. This
  repo's `CLAUDE.md` explicitly bans both ("No Respond.io or Wati hard
  dependency... No unofficial WhatsApp automation") and requires the
  official Meta WhatsApp Cloud API only. Notably, the old prototype's own
  later `docs/decisions/current-build-decisions.md` and its
  `MetaCloudWhatsAppAdapter` stub already agreed with the Meta-only
  stance — the conflict is with the *earlier* architecture/roadmap docs,
  not the prototype's final decision.
- **Live-integration timing — direct conflict.** The prototype's Month 2
  plan explicitly included "controlled go-live: enable live WhatsApp
  (Respond.io) and live LLM for a small volume of real UAE orders"
  (`Month-2-Live-Supervised-Operations.md`). This repo's `CLAUDE.md` keeps
  live WhatsApp/Stripe/LLM fully out of scope until explicitly approved,
  with live-WhatsApp readiness at position 5 of a 10-step build order,
  well after the admin UI and classifier.
- **LLM live-by-default — direct conflict.** The old spec's
  `.env.example` set `MOCK_LLM=false` by default, on the reasoning that
  "calls are cost-bounded" (`00-master-build-spec.md` §C.1.2). This
  repo's mock-first rule is stricter: no live LLM calls unless explicitly
  approved, full stop.
- **Approval policy — narrower in this repo.** The old 38-beat authority
  matrix marks many actions as fully agent-autonomous (routine
  rescheduling, routine cancellations, compensation-ladder-based SLA
  handling, review requests). This repo's rule is a stricter blanket
  policy: every agent-generated customer reply requires human approval in
  MVP, with no autonomy carve-outs yet.
- **Build sequence — different order.** The old master spec's Stage 1–5
  front-load a full 24-entity data model, RBAC/RLS, and multi-channel
  abstraction before Stage 6 (the actual agent) and Stage 7 (classifier).
  This repo intentionally builds the WhatsApp agent first and the
  classifier third, ahead of a fully generalized schema/auth layer.
- **Named third-party vendors not in scope.** The old spec names
  HubSpot, PandaDocs, Google Maps, Twilio number masking, and Stripe
  Connect as Phase 0 integrations (`00-master-build-spec.md` §B.9.4 area).
  None of these are approved or relevant to this repo's current
  mock-only stage.
- **Database — no conflict, confirms alignment.** Both the prototype and
  this repo agree strictly on PostgreSQL + pgvector + PostGIS +
  uuid-ossp as the core database, explicitly rejecting MySQL/Cloudflare
  D1. One caveat: the old prototype's actual backend reportedly never
  wired up PostGIS until a very late patch and had no `uuid-ossp` use in
  practice (`week-1-whatsapp-dashboard-start-report.md` §4) — a gap
  between the old spec's intent and its old implementation, worth
  avoiding by wiring these extensions in from the start here.
- **Known insecure states in the old prototype — do not repeat even
  temporarily.** Wide-open CORS (`allow_origins=["*"]`,
  `allow_credentials=False`, described as "safe by accident"), an
  `RLS ... USING (true)` policy that wasn't actually market-scoped, and
  **zero protected/authenticated endpoints for the entire documented life
  of the old backend** (repeated across nearly every security doc as the
  single biggest recurring risk) — this repo's `CLAUDE.md` doesn't yet
  have an explicit "auth from day one" rule, so this is worth flagging to
  the founder/team as a lesson learned, not just a passive note.
- **Approval queue with no producer.** For most of the old prototype's
  life, `create_approval_request` was imported but never actually called
  from the agent's send path — "a queue with no producer"
  (`current-prototype-reconciliation-report.md` §1/§16). This is exactly
  the failure mode this repo's rule 13 ("every risky action requires
  human approval") exists to prevent, and worth testing against directly
  once the approval flow is built or extended here.
- **Privacy firewall enforced inconsistently.** The old privacy/PII
  masking filter was wired into the WhatsApp demo endpoint but not into
  the booking agent path that actually created real orders and called the
  LLM (`current-prototype-reconciliation-report.md` §9) — a concrete
  example of the exact gap this repo's privacy-firewall rule needs
  guarded against with coverage on every LLM call site, not just one.

## 6. What should be reused (as inspiration, not code)

- The **`ChannelAdapter` interface pattern** — base class + fully mocked
  implementation + a live-provider stub that raises on instantiation — as
  the template for enforcing mock-first at the type level, for WhatsApp
  and eventually a `PaymentProvider` interface.
- The **approve-only-send invariant**: no code path other than the
  approval-approve handler (or a direct human reply) may trigger an
  outbound send — matches this repo's own approval rule and is worth
  enforcing architecturally, not just by convention.
- The **AIActionLog + CostTracking schema shape** (per-call detail +
  per-conversation rollup, 5-layer cost ceiling) whenever cost/logging
  work is extended.
- The **security-privacy-compliance-checklist.md tiered structure** and
  the **live-integration-approval-checklist.md** sign-off template —
  strong candidates to adapt into this repo's own
  `docs/checklists/security-privacy-compliance-checklist.md` and
  `docs/checklists/live-integration-approval-checklist.md`, since this
  repo currently has no equivalent of either.
- The **A/H/M authority-matrix concept** and the **role × tool permission
  matrix**, adapted into a future `docs/agents/tool-permissions.md` —
  useful once this repo's approval policy needs to move past "always
  require approval" toward selective autonomy.
- The **classifier taxonomy** (18 intents, 5-category sentiment + numeric
  score, sales-stage delta, routing rules, example prompt) as a concrete
  starting point when the Classifier Agent (build priority #3) is
  actually started.
- The **marketing/SEO agent-formula design** in full (per-agent spec
  template, disposition tags, dedup gate, verified-facts rule,
  three-cadence reporting) — still matches this repo's own future
  roadmap item (SEO/marketing agents), and is the most polished spec in
  the old docs.
- The **Order-State-Machine's DB-trigger-enforced transition model** and
  the **VDP / Facility-PPI / Driver-Score designs** for the future
  driver/VDP backend module (build-order item 7).
- The **Market Config "new market = config row, not code"** pattern for
  eventual multi-market work.
- The **privacy-firewall system-prompt rules** (never share PII with
  facility/driver, never quote an un-sourced price, never admit fault,
  identity-stability under prompt injection) to harden the WhatsApp
  Operations Agent's system prompt.
- The **pre-coding-checklist.md / week-1-reconciliation-checklist.md**
  structures as lightweight models for a "before starting a new module"
  gate checklist in this repo.

## 7. What should be ignored/discarded

- **Respond.io and Wati** as WhatsApp providers — directly banned by this
  repo's rules.
- The old **11-stage, schema-first, infrastructure-heavy build sequence**
  — front-loads a full data model/RBAC/RLS/multi-channel layer before any
  agent exists, the opposite of this repo's "ship the agent first" order.
- **LangGraph-migration urgency framing** and any of the old hand-rolled
  agent orchestration code/structure — this repo adopts LangGraph from
  scratch, nothing to migrate.
- **Railway/Vercel/Hetzner hosting discussion**, AWS S3/DigitalOcean
  Spaces, Kubernetes, GitHub Actions, Sentry, Metabase/Looker — superseded
  by this repo's Cloudflare-later direction.
- **`MOCK_LLM=false`-by-default** framing and any language treating live
  LLM calls as acceptable-by-default "since cost-bounded" — conflicts with
  this repo's stricter mock-first posture.
- The **beat-by-beat "Agent autonomous" grants** in the old 38-beat matrix
  (autonomous rescheduling, autonomous compensation-ladder application,
  autonomous review requests) — should not be implemented until this
  repo's own approval policy deliberately evolves past "every reply needs
  human approval."
- **Wide-open CORS, non-scoped RLS policies, and zero-auth endpoints** —
  documented failure states in the old prototype, not patterns to copy
  even temporarily.
- **"100+ country," "14 markets," multi-region/PIPL/China-region**
  ambitions (`00-master-build-spec.md` §B.1.3, §B.9.6, §B.10.3–B.10.4) —
  far beyond this repo's current single-agent-mock-mode scope; referencing
  these risks over-engineering.
- **Old test-count claims, delivery dates, and "current status" tables**
  in `backend/README.md`/`backend/DELIVERY_NOTES.md` and the audit
  reports — self-admittedly stale and contradictory even within the old
  docs; useful only as an example of what documentation drift looks like,
  not as a source of facts.
- **In-memory mock-data Next.js frontend** (`lib/mock-data.ts`,
  `AppProvider` context) — architecturally disconnected from any backend;
  per `CLAUDE.md` §3, only its layout/UX ideas (already reviewed
  separately for the admin UI build) are usable, not the code pattern.
- **Meeting/prompt template stubs** (`docs/prompts/*.md`,
  `docs/meetings/*.md`) — thin, mostly navigational, reference an
  Obsidian structure this repo's own `CLAUDE.md` §11–§12 documentation
  rules already supersede with a more detailed spec.
- **Named third-party vendors** (HubSpot, PandaDocs, Google Maps, Twilio,
  Stripe Connect, Alibaba Qwen) called out as concrete build targets in
  the old spec — none approved or relevant to this repo's current stage.

## Open questions for the founder/team

Two things surfaced repeatedly enough across the old docs that they're
worth a direct decision rather than silently resolving one way:

1. **Market scope** — is Qatar (or any market beyond a single initial
   one) still an active near-term target, or fully deferred? The old docs
   disagree with each other on this; this repo's `CLAUDE.md` is silent.
2. **Reporting cadence** — the old project had a standing "Friday written
   update, no exceptions" rule. This repo's `CLAUDE.md` requires weekly
   reports but doesn't pin a day — worth confirming if Friday should be
   the convention here too.
