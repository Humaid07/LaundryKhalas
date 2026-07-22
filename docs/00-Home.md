# LaundryKhalas — Documentation Home

Obsidian-style entry point for this vault. Start here.

## Project Memory

The single source of truth for how Claude Code should operate in this
repository is the repo-root [[CLAUDE|CLAUDE.md]] file (`../CLAUDE.md`).
It contains:

- Project identity and current build priority
- Core architecture decisions (backend, database, LLM, WhatsApp, frontend, Cloudflare)
- Non-negotiable engineering rules (mock-first, no live integrations without approval, no invented data)
- Risky-action / human-approval requirements
- Privacy firewall rules
- WhatsApp Operations Agent scope (what it does and does not do)
- Admin UI rules and design standard
- The mandatory documentation structure and required docs per task (see [[ADR-project-documentation-and-memory-rule]])
- Testing and git safety rules
- Deferred modules list and roadmap order

Every Claude Code session in this repo should read `CLAUDE.md` first and
follow it for the remainder of the task.

## Session Context Reconstruction

[[2026-07-21-new-claude-session-context-reconstruction]] —
`build-reports/2026-07-21-new-claude-session-context-reconstruction.md` — read-only
onboarding audit run after migrating to a new Claude account (no prior chat memory).
Reconstructs full project context from the repo alone: product goal, tech stack, the
two backends (legacy `app/` :8000 vs active `apps/whatsapp-agent/` :8100), all 10
dashboard sections, Operations 4-subsection IA, stateful mock order lifecycle, the
config/rules layer, functional global filters, mock/live status, known limitations
(no git repo, approvals not persisted server-side, no conversation inbox endpoint,
Windows `next build` quirk), and the next recommended build steps. No code changed.

## SEO Agents (Phase 1)

[[2026-07-22-seo-agent-dashboard-foundation]] —
`build-reports/2026-07-22-seo-agent-dashboard-foundation.md` — **SEO Agent foundation**:
16-agent catalog + runs/findings/recommendations/approval-tasks/change-log/reports in
`apps/whatsapp-agent/seo_agents/` (in-memory, mock-first, approval-gated, no live
sources), FastAPI `/api/seo/*`, typed dashboard client `seo-agent-api.ts`, and a live
Agent Fleet. Architecture: [[seo-agent-system]] · dashboard contract:
[[seo-agent-dashboard-contract]] · test script: [[seo-agent-test-script]].

## Latest Build Report

[[2026-07-22-customer-order-detail-redesign]] —
`build-reports/2026-07-22-customer-order-detail-redesign.md` — Customer Orders
cards now open a **dedicated full-page order workspace** at
`/operations/customer-orders/[orderId]` instead of a cramped right-side drawer:
header + breadcrumb + grouped actions, a scannable summary strip, and a 2-column
body (overview · items · pickup/delivery · **premium lifecycle timeline** · notes ·
related conversation · events) with a sticky sidebar (customer · payment ·
assignment · SLA · quick actions). Active status tab preserved on back; fully
responsive. Fixed a timeline bug where completed steps showed future timestamps.
Drawer pattern retained for the other 3 Operations subsections. Rule in
[[customer-order-detail-page]] / [[operations-navigation]]. **tsc 0 · 45/45 filter
tests · Playwright verified.**

[[2026-07-22-operations-workflow-tabs-refactor]] —
`build-reports/2026-07-22-operations-workflow-tabs-refactor.md` — Operations top
tabs are now **workflow/status views per subsection**, not subsection navigation.
Customer Facing + Drivers migrated onto the shared workspace pattern
(`WorkflowTabs → RecordCard → DetailDrawer`); standalone action panels removed —
actions live only inside a record's detail drawer; dead `OperationsSubNav`
deleted. Rule documented in [[operations-navigation]]. **tsc 0 + Playwright verified.**

[[2026-07-22-whatsapp-booking-state-machine]] —
`build-reports/2026-07-22-whatsapp-booking-state-machine.md` — replaces the
hallucinating stateless order-capture with an explicit **persisted booking state
machine** (`services/booking_flow.py`): "I need a laundry pickup" now only detects
intent and sends the interactive service list — no assumed service/date/area. DB
is the source of truth; slots come from a new DB-backed `pickup_slots` table;
Evolution v2.3.7 interactive lists/buttons with a numbered-text fallback; webhook
idempotency; operational order created exactly once on explicit confirm. Migration
000005 (+ applied the stranded 000004). **263 tests pass**, live-verified.

[[2026-07-22-sidebar-subnavigation-refactor]] —
`build-reports/2026-07-22-sidebar-subnavigation-refactor.md` — **Hierarchical sidebar
navigation**: converted the flat left sidebar into a nested, expand/collapse tree where
every section's subsections (Operations ▸ Customer Facing / Facility Facing / Drivers /
Customer Orders, and the same for SEO Agents, Marketing, Partner Acquisition, Finance,
Dev & Automation, Reports, Settings) are reachable directly from the sidebar. Parent stays
highlighted on child routes; active child is filled + railed; badges at both levels;
auto-expand of the active section; collapsed + mobile preserved. Replaced the Operations
big-card landing with a clean **Operations Overview** (KPIs, urgent alerts, recent activity,
quick links). Children derived from `sections.ts` (no route changes). **tsc 0 errors + live
Playwright verified.** See [[dashboard-navigation]].

[[2026-07-22-service-taxonomy-sync]] —
`build-reports/2026-07-22-service-taxonomy-sync.md` — **Service taxonomy synced to the
live website**: replaced the four disjoint service lists with ONE canonical catalog of
the **8 real LaundryKhalas services** (crawled from `laundrykhalas.com/en-ae/personal-laundry/`,
incl. the newly-found **Luxury Bag Spa**) in `config/laundry_services.json`, read by the
WhatsApp agent, order extraction, Supabase (`service_id`/`unit_type`/`requires_manual_quote`
columns), the dashboard filters (TS mirror), and the SEO agents. Adds an **"ask, don't
guess" service selection** (bare "laundry pickup" now asks which service), pricing safety
(manual-quote services never auto-priced), a `/api/service-taxonomy` catalog + **sync-check
CLI + `/health` endpoint** driving a dashboard **"Service taxonomy mismatch detected."**
warning. **245 backend tests + sync CLI green; admin tsc 0 errors, filters 45/45.** See
[[service-taxonomy]].

[[2026-07-22-whatsapp-supabase-order-capture]] —
`build-reports/2026-07-22-whatsapp-supabase-order-capture.md` — **WhatsApp → Supabase
order capture**: an extraction/order-state layer turns approved Evolution test chats
into structured data. Backfills customer profile (name/city/area/address, address
backend-only), creates/updates a per-conversation **draft order** that accumulates
across turns and is confirmed → `pickup_scheduled` (IDs `LC-TEST-####`), writes
`order_events` (created/service/items/address/pickup/payment/confirmed), and raises a
**flag + ticket** on escalations (never auto-resolved). Adds live dashboard panels on
`/operations/customer-orders` and `/operations/customer-facing` behind
`NEXT_PUBLIC_USE_LIVE_WHATSAPP_INBOX` (Dashboard → FastAPI → Supabase). **208 tests**,
tsc/eslint/ruff clean, live-Supabase integration verified (auto-cleaned). Builds on
[[2026-07-22-evolution-sender-allowlist]].

[[2026-07-22-evolution-sender-allowlist]] —
`build-reports/2026-07-22-evolution-sender-allowlist.md` — **safety fix**: the
Evolution auto-reply now only replies to numbers on `EVOLUTION_ALLOWED_TEST_NUMBERS`
(normalized E.164), and only for safe, laundry-related messages. Non-allowed
senders are dropped (no store, no agent, no send, `200 OK`); escalations stay
human-gated. Builds on [[2026-07-22-auto-reply-decision-layer]]. 195 tests pass.

[[2026-07-21-evolution-whatsapp-adapter]] —
`build-reports/2026-07-21-evolution-whatsapp-adapter.md` — builds the **Evolution
API WhatsApp adapter** (current provider, `WHATSAPP_MODE=evolution`, mock by
default). Adds `channels/evolution_whatsapp.py` (`send_text` →
`POST /message/sendText/{instance}`; `parse_evolution_webhook`), an inbound
webhook `POST /webhooks/evolution` that upserts customer+conversation into the
**Supabase inbox**, stores the message, drafts a reply and **flags escalations**
(refund→urgent/Finance, etc.), and outbound live send wired into the inbox
`human-message` endpoint (gated by `evolution_live_ready`). Agent never
auto-sends by default (`EVOLUTION_AUTO_REPLY=false`); the sanctioned live path is
a human operator reply. Privacy kept: full number only in `phone_e164`
(backend-only) + `phone_hash`, APIs return `masked_phone`. `pytest` **174
passed**, ruff clean; **live-verified** inbound round-trip against the running
Evolution server + dev/test Supabase (masked phone, refund flag, no leak).
See [[evolution-whatsapp-integration]].

Previous: [[2026-07-21-supabase-dev-test-setup]] —
`build-reports/2026-07-21-supabase-dev-test-setup.md` — sets up the **separate
dev/test Supabase project** as the WhatsApp Agent database (Dashboard → FastAPI →
Supabase; NOT production). Adds `supabase/migrations/*` (10 tables — customers,
conversations, messages, orders, order_events, agent_flags, human_takeovers,
approval_queue, tickets, agent_logs — UUID PKs, indexes, `updated_at` triggers,
RLS enabled, and 7 test-data marker columns) + an idempotent fake/demo **seed**
(6 customers, 6 conversations, 18 messages, 5 orders `LK-AE-1024/25/26/27/2031`,
5 flags, 2 takeovers, 3 tickets…). Adds **37 scenario fixtures**
(`apps/whatsapp-agent/test-data/scenarios/`), env-gated **seed/reset/verify**
scripts (refuse outside dev/test; reset deletes only
`is_test_data & created_by_seed`, never truncates), a **`db/` repository layer**
(asyncpg; `DATABASE_MODE=supabase`) with graceful SQLite fallback, new FastAPI
endpoints (`/health/db`, `/api/conversations/*`, `/api/flags/*`, order
mode-branch), and prepared dashboard client methods + **Test Data / Demo
Conversation** badges. `pytest` **155 passed**, ruff clean, `tsc` 0. **Live
Supabase verification is pending credentials.** No live WhatsApp/Stripe/LLM; no
secrets committed. See [[supabase-dev-database]], [[test-data-strategy]],
[[supabase-whatsapp-agent-test-script]].

Previous: [[2026-07-21-global-filters-all-sections]] —
`build-reports/2026-07-21-global-filters-all-sections.md` — makes the dashboard's
**global filters truly global** across every section, subsection and tab. Closes the
coverage gaps where tables/KPIs/charts rendered raw data behind a visible filter bar:
adds structured `city`/`channel`/`scope` fields to previously geo-less mock arrays
(facility/driver/order issues, B2B invoices, SEO tasks), broadens the engine's
date-field recognition (`DATE_KEYS`), wires every inert list through
`applyGlobalFilters` with filter-aware empty states, and honestly labels
non-recomputable aggregates with a new **"Overall snapshot"** badge (`SnapshotBadge`)
— section variants "Global / site-wide" (SEO), "Brand-wide" (Marketing),
"Global / technical" (Dev). Region→Market→City cascade + cross-nav persistence
confirmed. Status/Owner stay **local** (domain-specific); Settings stays unfiltered.
Verified: `tsc` clean, **45** engine assertions, all routes HTTP 200, Playwright
filter-behaviour + persistence with **0 console errors**. Mock-only; no privacy
surface changed. See [[dashboard-filter-system]] and
[[internal-dashboard-ui-test-script]].

Previous: [[2026-07-21-whatsapp-agent-inbox-ui]] —
`build-reports/2026-07-21-whatsapp-agent-inbox-ui.md` — replaces the WhatsApp Agent
**test console** in the dashboard with a real **WhatsApp-style inbox** (Operations →
Customer Facing → WhatsApp Agent): left chat list (search, filter chips + counts,
status/urgent badges, order id), right conversation pane (masked-phone header,
WhatsApp bubbles, internal-note cards), and an xl context panel (handoff flag card
with reason/team/suggested reply + privacy-safe order summary). **Human takeover is
gated** — the composer only appears after **Take over** (offered when the agent
raises a flag or the operator opts in); **Return to bot** / **Mark resolved** manage
state. **Removed** the test-message box, preset "customer" messages, and the
backend-wired "Live Agent Console"; the dashboard can no longer author customer
messages. Frontend-seeded mock (8 scenarios); state mutations map 1:1 to the future
`/api/conversations*` contract. New: `lib/dashboard/whatsapp-inbox.ts` +
`components/dashboard/whatsapp/*`; `formatClock` added. Playwright light/dark/mobile:
inbox behaviour verified, **0 console errors, 0 overflow**; this build's files are
`tsc`-clean (87 pre-existing filter-engine errors are unrelated and untouched). Mock
only; phones masked, area/city only. See [[whatsapp-agent-dashboard-inbox]] and
[[whatsapp-agent-inbox-test-script]].

Previous: [[2026-07-21-laundry-class-whatsapp-agent]] —
`build-reports/2026-07-21-laundry-class-whatsapp-agent.md` — builds the **Laundry Class
WhatsApp agent** in `apps/whatsapp-agent/laundry_class/` (self-contained, existing 95 tests
untouched): a **file knowledge base** with the **official Laundry Class prices** (founder
directive, tests adapted), a **LangChain + LangGraph** state machine with a **persistent
SQLite checkpointer** keyed by `thread_id = whatsapp:<phone>` (isolated, restart-surviving
memory per number), **15-intent routing**, progressive **order collection**, dummy-order
**status/recall**, **delivery reschedule** (never falsely confirmed), and a **human-handoff**
workflow with a structured once-per-case admin notification. Mock-first (deterministic
LangChain `BaseChatModel`, no LLM/WhatsApp/Stripe calls); masked logs. **13/13** e2e tests
(TC1–TC10 + isolation + restart), full repo **142 passed**, ruff clean. Test report:
`apps/whatsapp-agent/whatsapp_agent_test_report.md`; memory-separation note:
[[laundry-class-memory-separation]]; demo: [[week-01-laundry-class-agent-demo]].
Known limitation: TC9 item re-description over-counts the estimate (still labelled an
estimate, no invented price), resolved by the swappable live-LLM node.

Previous: [[2026-07-21-operations-subsection-pages]] —
`build-reports/2026-07-21-operations-subsection-pages.md` — restructures
**Operations** from one crowded page into a **landing page + four subsection
routes**: `/operations` shows four section cards, and
`/operations/{customer-facing,facility-facing,drivers,customer-orders}` each get
their own focused page with breadcrumb + pill sub-nav (`OperationsSubNav`). Adds
a dedicated **Customer Orders** order center (10 KPIs; All/Active/Completed/
Cancelled/Issues/Changes tabs; global + local status/payment filters). Existing
Customer Facing / Facility Facing / Drivers components reused as-is; Customer
Facing swaps its Orders tab for **Conversations** and keeps the WhatsApp Agent
console; **Payments removed from Operations** (now in Finance & Compliance).
Also fixes a repo-wide React #425 hydration mismatch by making
`formatRelativeTime` deterministic (`MOCK_NOW`). Typecheck 0; isolated prod build
24/24; Playwright light/dark/mobile → **0 console errors, 0 hydration errors, 0
overflow**. Privacy firewall + WhatsApp console preserved. Mock-only. See
[[internal-dashboard-ui]] and [[internal-dashboard-ui-test-script]].

Previous: [[2026-07-21-filter-dropdown-redesign]] —
`build-reports/2026-07-21-filter-dropdown-redesign.md` — replaces the generic
native `<select>` filters with one reusable custom **`FilterSelect`** dropdown
(rounded-full pill trigger, `rounded-2xl` popover, rose active/selected state +
check, right-edge auto-flip, rose focus ring, full keyboard/Escape/outside-click
a11y). Wired into **both** the global `FilterBar` and the `LocalFilterBar`; the
filter engine, chips, Clear all and the Market→City dependency are unchanged.
Typecheck clean; compiled + 24/24 pages generated; Playwright-verified on `/sales`
(light/dark/mobile, 0 console errors, no overflow). Production `next build` exits
on a Windows-only `500.html` rename race (unrelated). UI-only, mock-only. See
[[internal-dashboard-ui]] and [[internal-dashboard-ui-test-script]].

Previous: [[2026-07-21-dashboard-partner-finance-compliance-dev-automation]] —
`build-reports/2026-07-21-dashboard-partner-finance-compliance-dev-automation.md` —
extends the dashboard shell from 8 to **10 top-level sections**: adds **Partner
Acquisition** (4 role cards, 12 KPIs, 8 charts, 7 tabs — pipeline, market
intelligence, outreach, meetings, compliance queue, regional coverage, partner
performance preview), renames **Finance → Finance & Compliance** (13 financial +
10 compliance KPIs, 9 tabs incl. facility/driver compliance, documents & expiry,
audit trail, risk flags; `/finance` redirects to `/finance-compliance`), and adds
**Dev & Automation** (14 KPIs, 8 charts, 9 tabs — agent health for 22 agents,
technical issues, API/webhook health, job queue, LLM/cost usage, deployments,
integrations, logs). New reusable `LocalFilters` (used where global geo doesn't
apply). Reports gains 3 cards; Settings gains 7 connected apps. Typecheck + build
+ lint clean; Playwright-verified light/dark/mobile (0 console errors, 0 overflow
on the new pages). Mock-only, UI-only, no live integrations. See
[[internal-dashboard-ui]] and
[[internal-dashboard-partner-finance-dev-test-script]].

Previous: [[2026-07-21-operations-drivers-payments-sections]] —
`build-reports/2026-07-21-operations-drivers-payments-sections.md` — expands
**Operations** from 2 to **4 top-level surfaces**: adds **Drivers** (pickup/
delivery fleet — 10 KPIs, driver overview, pickup/delivery queues with area-only
privacy, performance, issues) and **Customer Charges / Payments** (operational
customer-level payment view — 10 KPIs, payment overview, pending payments, refund
requests, adjustments, payment issues, B2B invoices; mock-only, Stripe off, human
approval required). Existing Customer Facing & Facility Facing untouched.
Typecheck + build + lint clean; browser-verified light/dark/mobile (no overflow).
Mock-only, UI-only. See [[internal-dashboard-ui]] and
[[internal-dashboard-ui-test-script]].

Previous: [[2026-07-20-whatsapp-agent-stateful-orders]] —
`build-reports/2026-07-20-whatsapp-agent-stateful-orders.md` — makes the
standalone WhatsApp agent (`apps/whatsapp-agent`, :8100) **humanized and
stateful**: a WhatsApp-style **typing indicator** (configurable 2–3s) in the
chat UI, and — the key change — the conversation now **updates a real,
queryable order state behind the scenes**. New `Order` model + `order_store`
service with a full mock lifecycle (`draft → active → … → completed /
cancelled`, plus cancellation/pickup-change requests), a deterministic
`order_flow` that reads+mutates orders for **book / track / cancel / change
pickup / add items**, seeded **dummy orders LK-AE-1024..1027**, and an
**order/dashboard API** (`/api/orders/active|completed|metrics|{id}|complete|
status`). Booking collects service → items → area → time → confirm and creates
an **active** order; track returns the real status and refuses unknown IDs;
cancel never auto-cancels. **129 backend tests pass** (+34); typecheck + lint
clean; live startup verified. Mock-only. See
[[whatsapp-agent-memory-and-orders]], [[mock-order-lifecycle]] and
[[whatsapp-agent-stateful-order-test-script]].

Previous: [[2026-07-20-whatsapp-agent-rules]] —
`build-reports/2026-07-20-whatsapp-agent-rules.md` — adds a **business & safety
rules config layer** to the standalone WhatsApp agent (`apps/whatsapp-agent`,
:8100): six `config/*.json` files (master rules, services+pricing, quick actions,
escalation, mock-mode wording, tone) loaded through one cached leaf module
`rules.py`, so domain scope, welcome/refusal text, the service menu, human
handoff, demo-mode honesty and tone are all edited in config, not hardcoded.
Adds a deterministic **escalation/handoff** path (complaint, refund, damage,
missing item, late delivery, payment, B2B, legal, anger → hands to the team, no
autonomous action), **PII masking** in the audit log, and enriched logging.
Behaviour preserved; pricing de-duplicated to one source. 117 backend tests pass
(+22 new); live mock server restarted & verified. See [[whatsapp-agent-rules]]
and [[whatsapp-agent-rule-test-script]]. Mock-only.

Previous: [[2026-07-20-global-filters-functional]] —
`build-reports/2026-07-20-global-filters-functional.md` — makes the global filter
bar (Date/Market/Region/City/Channel/Service) **actually filter the data**: a
shared in-memory filter store (React Context) + a controlled FilterBar with active
chips and Clear, and a pure filter engine (`lib/dashboard/filters.ts`). Tables,
lists and categorical charts on Overview, Operations (both teams), Sales and
Finance re-slice live (facility views stay PII-safe). Headline KPI trend cards and
time-series stay as period snapshots (documented); SEO's dead filter bar removed.
Typecheck + build pass; Playwright-verified (City=Dubai → 3 Dubai orders;
Service=Dry Cleaning across both Operations teams; persists across nav) with 0
console errors. Mock-only.

Previous: [[2026-07-20-operations-team-split]] —
`build-reports/2026-07-20-operations-team-split.md` — splits the **Operations**
section into two teams via a segmented top switch: **Customer Facing** (WhatsApp
console, customer orders, tickets, order changes, cancellations, follow-ups) and
**Facility Facing** (facility order queue, assignment + management, status
updates, issues, quality checks, delivery handoff). Each team has distinct KPIs,
tables, activity and actions. **Facility views enforce the privacy firewall by
construction** — area/city only, no customer name/phone/email/address (verified:
0 phone-like strings leak). Typecheck + build pass; browser-verified in
light/dark/mobile with 0 console errors. See
[[ADR-operations-customer-facing-facility-facing]]. Mock-only.

Previous: [[2026-07-20-settings-notification-toggle-fix]] —
`build-reports/2026-07-20-settings-notification-toggle-fix.md` — fixes the
broken **Settings → Notification preferences** card (toggles misaligned /
clipped on the right, cramped spacing, weak dark-mode contrast). Root cause was
shared: the row label lacked `min-w-0 flex-1` (long labels pushed/clipped the
switch) and the `Switch` component took no `className` and used a too-faint
unchecked track. Fixed once in the shared `Switch` (`components/dashboard/ui/Switch.tsx`)
and applied to **both** the Notification preferences and Agent settings cards.
Typecheck + production build pass; browser-verified in light + dark + mobile —
toggles fully visible and aligned, long labels wrap, no horizontal overflow.
Mock-only, UI-only.

Previous: [[2026-07-20-whatsapp-agent-into-operations]] —
`build-reports/2026-07-20-whatsapp-agent-into-operations.md` — wires the
existing standalone WhatsApp Agent backend (`apps/whatsapp-agent`, :8100) into
the dashboard's **Operations → WhatsApp Agent** tab as a **Live Agent Console**:
health chip, real send → drafted reply → human approval gate (Approve / Edit /
Reject / manual takeover), interactive action buttons attached to the agent
message, and a mock/live status panel. Added `:3000` to the backend's CORS
origins. Typecheck + build pass; browser-verified end-to-end (in-domain approve
flow + out-of-domain refusal) with 0 console errors. Mock-only.

Previous: [[2026-07-20-internal-dashboard-structure]] —
`build-reports/2026-07-20-internal-dashboard-structure.md` — the real
**Internal Dashboard (Command Center)** structure built inside `apps/admin`:
a rose/white design system with full dark mode, a reusable component library,
and all eight sections (Overview, Operations, Sales, SEO Agents, Marketing,
Finance, Reports, Settings) on LaundryKhalas-specific mock data. Typecheck +
production build pass; browser-verified with **0 console errors** across all
pages in light/dark/mobile, charts recolor on theme switch, tables convert to
cards on mobile. Mock-only — no live APIs, no secrets. See
[[internal-dashboard-ui]] and [[ADR-internal-dashboard-design-system]].

Previous: [[2026-07-18-whatsapp-interactive-message-actions]] —
`build-reports/2026-07-18-whatsapp-interactive-message-actions.md` —
corrects the standalone WhatsApp Agent's quick actions: moved from a
permanent toolbar/dropdown above the composer to WhatsApp-style
interactive buttons attached to the specific agent message asking a
question (welcome message → main menu; "which service?" → service menu),
per explicit instruction. Two real bugs found and fixed in the process -
see [[standalone-whatsapp-agent]] and the build report's bug log.

Previous: [[2026-07-18-classifier-escalation-wiring]] —
`build-reports/2026-07-18-classifier-escalation-wiring.md` — wires the
WhatsApp Operations Agent to escalate instead of running its happy-path
order flow when the Classifier Agent flags a conversation (complaint,
cancellation, rescheduling, payment issue, B2B lead, urgent/angry
sentiment). Fixed a real bug found in the process: a rescheduling message
with all three order slots present would otherwise have created a
duplicate order. Explicit founder/team follow-up, same day as the
Classifier Agent build below.

Earlier: [[2026-07-18-classifier-agent]] —
`build-reports/2026-07-18-classifier-agent.md` — the Classifier Agent
(`app/agents/classifier/`, main system): 18-intent/5-sentiment
classification plus CLAUDE.md §9's routing flags, running automatically
ahead of the WhatsApp Operations Agent. Explicit founder/team instruction
to resume the main roadmap (build priority #3) after the standalone-agent
detour - see [[classifier-agent]] and
[[classifier-agent-design-decisions]].

Earlier: [[2026-07-18-standalone-whatsapp-agent]] —
`build-reports/2026-07-18-standalone-whatsapp-agent.md` — a second,
independent WhatsApp agent (`apps/whatsapp-agent/` + `apps/whatsapp-chat/`),
domain-guarded to laundry/cleaning/LaundryKhalas only, built per an
explicit founder/team redirection ahead of the classifier agent - see
[[ADR-standalone-whatsapp-agent-first]].

Earlier: [[2026-07-18-admin-ui-build]] —
`build-reports/2026-07-18-admin-ui-build.md` — retroactive build report
for the Admin UI, plus a live re-verification of the full mock WhatsApp →
agent → approval → order flow and all 8 Admin UI routes.

## Latest Weekly Report

[[week-01-report]] — `weekly-reports/week-01-report.md`

## Latest Presentation Notes

[[week-01-whatsapp-agent-stateful-demo]] —
`presentation-notes/week-01-whatsapp-agent-stateful-demo.md`

Previous: [[week-01-internal-dashboard-demo]] —
`presentation-notes/week-01-internal-dashboard-demo.md`

Previous: [[week-01-classifier-agent-demo]] —
`presentation-notes/week-01-classifier-agent-demo.md`

Previous: [[week-01-standalone-whatsapp-agent-demo]] —
`presentation-notes/week-01-standalone-whatsapp-agent-demo.md`

Earlier: [[week-01-admin-ui-demo-notes]] —
`presentation-notes/week-01-admin-ui-demo-notes.md`

## Key Architecture Docs

- [[internal-dashboard-ui]] — `architecture/internal-dashboard-ui.md`
- [[classifier-agent]] — `architecture/classifier-agent.md`
- [[standalone-whatsapp-agent]] — `architecture/standalone-whatsapp-agent.md`
- [[whatsapp-agent-rules]] — `architecture/whatsapp-agent-rules.md`
- [[whatsapp-agent-memory-and-orders]] — `architecture/whatsapp-agent-memory-and-orders.md`
- [[mock-order-lifecycle]] — `architecture/mock-order-lifecycle.md`
- [[whatsapp-cloud-api-integration]] — `architecture/whatsapp-cloud-api-integration.md`
- [[domain-guard]] — `architecture/domain-guard.md`
- [[dashboard-navigation]] — `architecture/dashboard-navigation.md` (hierarchical sidebar + page tabs)
- [[operations-navigation]] — `architecture/operations-navigation.md` (sidebar = subsection, top tabs = workflow/status, actions in drawer)
- [[service-taxonomy]] — `architecture/service-taxonomy.md` (live 8-service catalog, single source of truth)
- [[whatsapp-agent-architecture]] — `architecture/whatsapp-agent-architecture.md`
- [[admin-ui-architecture]] — `architecture/admin-ui-architecture.md`
- [[privacy-firewall]] — `architecture/privacy-firewall.md`

## Key Decision Docs

- [[ADR-operations-customer-facing-facility-facing]] — `decisions/ADR-operations-customer-facing-facility-facing.md`
- [[ADR-internal-dashboard-design-system]] — `decisions/ADR-internal-dashboard-design-system.md`
- [[classifier-agent-design-decisions]] — `decisions/classifier-agent-design-decisions.md`
- [[ADR-standalone-whatsapp-agent-first]] — `decisions/ADR-standalone-whatsapp-agent-first.md`
- [[current-build-decisions]] — `decisions/current-build-decisions.md`
- [[admin-ui-design-decisions]] — `decisions/admin-ui-design-decisions.md`
- [[ADR-project-documentation-and-memory-rule]] — `decisions/ADR-project-documentation-and-memory-rule.md`

## Checklists

- [[internal-dashboard-ui-test-script]] — `checklists/internal-dashboard-ui-test-script.md`
- [[standalone-whatsapp-agent-test-script]] — `checklists/standalone-whatsapp-agent-test-script.md`
- [[whatsapp-agent-rule-test-script]] — `checklists/whatsapp-agent-rule-test-script.md`
- [[whatsapp-agent-stateful-order-test-script]] — `checklists/whatsapp-agent-stateful-order-test-script.md`
- [[live-whatsapp-readiness]] — `checklists/live-whatsapp-readiness.md`
- [[admin-dashboard-mvp]] — `checklists/admin-dashboard-mvp.md`
- [[admin-ui-manual-test-script]] — `checklists/admin-ui-manual-test-script.md`
- [[service-taxonomy-test-script]] — `checklists/service-taxonomy-test-script.md`

## Audits

- [[fresh-project-start-report]] — `audits/fresh-project-start-report.md`
- [[admin-ui-start-report]] — `audits/admin-ui-start-report.md`
- [[prototype-md-review]] — `audits/prototype-md-review.md` — full review of
  all 92 Markdown files in the old `LaundryKhalasPrototype` repo, compared
  against this repo's `CLAUDE.md`; flags two open questions for the
  founder/team (market scope, reporting cadence day).

## Also See

- `README.md` (this folder) — flat index of docs with short descriptions.
- Repo-root `README.md` — how to actually run the project.
