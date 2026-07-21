# Build Report — New Claude Session Context Reconstruction

- **Date:** 2026-07-21
- **Type:** Context reconstruction / onboarding audit (no code changes)
- **Trigger:** Migrated to a new Claude account; previous chat history unavailable. Repo, docs, and build reports are the source of truth.

## Objective

Rebuild full project context from the local repository only — no reliance on
prior chat memory — and produce a single reference summary of what already
exists, its mock/live status, and the next recommended build step. **No code was
written or modified during this task.**

## Method

Read-only inspection of: `CLAUDE.md`, `README.md`, `docs/00-Home.md`,
`docs/architecture/`, `docs/build-reports/`, `docs/checklists/`,
`docs/decisions/`, `docs/presentation-notes/`, and the live app structure under
`apps/` and `app/`. The repo is **not a git repository** (no `.git`), so history
was reconstructed from dated build reports.

---

## 1. Current Product Goal

LaundryKhalas is a **WhatsApp-first, AI-powered laundry & cleaning operations
platform** — not just a chatbot. The long-term system is an agentic operations OS
serving customers, internal ops, partner facilities, drivers, and admins across
UAE/GCC markets. Current build priority (per `CLAUDE.md`): the **WhatsApp
Operations Agent** + an **internal admin dashboard** for visually testing it,
with an **approval / manual-takeover** workflow, mock orders, mock facility
assignment, AI action logging, and presentation-ready weekly docs.

## 2. Current Tech Stack (as built)

- **Frontend / dashboard (`apps/admin`):** Next.js 14.2 (App Router), React 18,
  TypeScript, Tailwind CSS 3.4, Recharts, `next-themes`, `@tanstack/react-query`,
  lucide-react. Custom shadcn-style component library. Dev port **:3000**.
- **Chat UI (`apps/whatsapp-chat`):** Next.js, WhatsApp-like UI, typing
  indicator, message-attached interactive buttons. Dev port **:3100**.
- **Active agent backend (`apps/whatsapp-agent`):** Python + FastAPI, SQLAlchemy
  async, SQLite (local mock DB), Pydantic. LangChain + LangGraph for the newer
  "Laundry Class" agent. Runs on **:8100** (uvicorn). `.venv` present.
- **Legacy backend (`app/`, repo root):** the original FastAPI system (Postgres +
  PostGIS + pgvector + Redis + Celery via `docker-compose.yml`, port **:8000**)
  that contains the **Classifier Agent** and the original WhatsApp Operations
  agent. Kept as reference; not the active dev target.
- **Planned (not yet used):** PostgreSQL/pgvector/PostGIS as source of truth,
  Alembic migrations, Cloudflare (Pages/Workers/R2/AI Gateway), Meta WhatsApp
  Cloud API, Stripe.

## 3. Current App Structure

```
D:\Laundry Khalas App
├── app/                     legacy FastAPI system (:8000, Postgres/Celery) — classifier lives here
├── apps/
│   ├── admin/               internal dashboard (Next.js, :3000) — ACTIVE
│   ├── whatsapp-agent/      standalone agent backend (FastAPI, :8100) — ACTIVE
│   │   ├── api/             chat, orders, settings, webhooks routers
│   │   ├── services/        order_store, escalation, domain_guard, privacy, storage
│   │   ├── config/          6 JSON rule files + scenarios/
│   │   ├── laundry_class/   LangGraph agent (graph, flows, intents, slots, KB, handoff)
│   │   ├── channels/        mock_whatsapp, meta_whatsapp (stub), whatsapp_base
│   │   ├── llm/             service + providers (mock active)
│   │   └── tests/           12 test modules
│   └── whatsapp-chat/       WhatsApp-like chat UI (Next.js, :3100) — ACTIVE
├── docs/                    architecture, build-reports, checklists, decisions, weekly-reports, presentation-notes
├── docker-compose.yml       legacy stack (postgres/redis/api/celery)
└── CLAUDE.md                project memory & engineering rules (source of truth)
```

Two WhatsApp backends coexist by design: **legacy `app/`** (has the Classifier)
and **active `apps/whatsapp-agent/`** (standalone, stateful orders, Laundry Class
LangGraph agent). New work targets `apps/whatsapp-agent`.

## 4. Dashboard Sections Already Built

10 top-level sidebar sections (`apps/admin/lib/dashboard/nav.ts`), each moving
toward a **landing page + subsection routes** pattern:

1. **Overview** — command-center KPIs.
2. **Operations** — landing + 4 subsections: `customer-facing`, `facility-facing`,
   `drivers`, `customer-orders` (see §6).
3. **Sales** — overview, markets, channels, services, funnel, B2B/B2C, top customers.
4. **Partner Acquisition** — pipeline, market intelligence, outreach, meetings,
   compliance queue, regional coverage, performance preview, team.
5. **SEO Agents** — fleet, content pipeline, GSC, hyperlocal, technical, indexing,
   competitors, AI search, reports.
6. **Marketing** — campaigns, content calendar, creative studio, social, PR,
   influencer/UGC, platform analytics, UTM, approvals.
7. **Finance & Compliance** — financial overview, customer payments, refunds,
   cost breakdown, facility/driver compliance, documents & expiry, audit trail,
   risk flags. (`/finance` → 307 redirect to `/finance-compliance`.)
8. **Dev & Automation** — agent health (22 agents), technical issues, API/webhook
   health, job queue, LLM/cost usage, deployments, integrations, logs/audit.
9. **Reports** — daily standup, monthly executive, per-domain report pages.
10. **Settings** — profile/team, roles/permissions, markets, notifications,
    agent guardrails, connected apps, theme.

There is also a separate legacy admin surface under `apps/admin/app/admin/*`
(conversations, approvals, orders, ai-logs, mock-whatsapp) wired to the API.

**Design system:** rose/white, full dark mode, reusable components
(`components/dashboard/*`), custom `FilterSelect` dropdown, status chips,
responsive tables→cards. **UI must read production-ready — no mock/demo/dummy/test
words** (owner directive; vocabulary: Staged / Standby / Coming soon / Review
mode / Operational).

## 5. WhatsApp Agent Status

- **Standalone agent (`apps/whatsapp-agent`, :8100)** — active. Mock-first
  (mock WhatsApp adapter, mock LLM provider). Domain-guarded to laundry/cleaning.
- **Config/rules layer** — 6 JSON files (`whatsapp_agent_rules`,
  `laundry_services`, `quick_actions`, `escalation_rules`, `mock_mode_rules`,
  `agent_tone_rules`) loaded through cached `rules.py`. Domain scope, wording,
  service menu, handoff, tone all editable in config.
- **Escalation/handoff** — deterministic path for complaint, refund, damage,
  missing item, late delivery, payment, B2B, legal, anger → acknowledge + hand to
  team, **no autonomous resolution**.
- **PII masking** — phone/email masked in audit logs (`services/privacy.py`).
- **Stateful orders** — real `Order` model + `order_store` with a full mock
  lifecycle; conversation mutates order state for book/track/cancel/change-pickup/
  add-items. Seeded demo orders **LK-AE-1024..1027**.
- **Order/dashboard API** — `/active`, `/completed`, `/metrics`, `/{id}`,
  `/{id}/complete`, `/{id}/status`, plus `/api/test-chat/message`, `/api/messages`,
  `/api/settings/status`, `/webhooks/whatsapp`.
- **Laundry Class LangGraph agent (`laundry_class/`)** — self-contained
  LangChain/LangGraph state machine, file KB with **official Laundry Class
  prices**, persistent SQLite checkpointer keyed `thread_id = whatsapp:<phone>`
  (isolated, restart-surviving memory), 15-intent routing, order collection,
  status/recall, delivery reschedule (never falsely confirmed), human handoff.
  13/13 e2e tests. Known limitation: TC9 item re-description over-counts the
  estimate (still labelled an estimate).
- **Classifier Agent** — exists in the **legacy `app/agents/classifier/`** only
  (18-intent/5-sentiment + routing flags). Not yet ported to the standalone agent;
  a scenario/evaluation pack is needed before a fresh classifier build.

## 6. Operations Dashboard Status

`/operations` is a **landing page with 4 subsection cards**, each a focused route
with breadcrumb + pill sub-nav (`OperationsSubNav`):

- **Customer Facing** — WhatsApp Agent live console (send → drafted reply →
  approve/edit/reject/manual takeover), conversations, tickets, changes,
  cancellations, follow-ups.
- **Facility Facing** — facility order queue, assignment/management, status,
  issues, quality checks, delivery handoff. **Privacy firewall by construction**
  (area/city only, no customer name/phone/email/address).
- **Drivers** — pickup/delivery fleet, queues (area-only privacy), performance,
  issues.
- **Customer Orders** — dedicated order center (10 KPIs; All/Active/Completed/
  Cancelled/Issues/Changes tabs; global + local status/payment filters).

Payments were **removed from Operations** and now live under Finance & Compliance.
The Customer Facing console is wired to the live `apps/whatsapp-agent` backend
(:8100) with a health chip; `:3000` is in the backend CORS allow-list.

## 7. Order State / Mock Order Lifecycle Status

Real `Order` model in `apps/whatsapp-agent/models.py` with `order_store` service.
Lifecycle: `draft → active → … → completed / cancelled`, plus cancellation and
pickup-change **requests** (agent never auto-cancels). Booking collects
service → items → area → time → confirm and creates an **active** order; track
returns real status and refuses unknown IDs. Seeded demo orders LK-AE-1024..1027
on fresh DB (idempotent, on app startup). Architecture: `mock-order-lifecycle.md`,
`whatsapp-agent-memory-and-orders.md`.

## 8. Rules / Config Layer Status

Config-driven, not hardcoded. `apps/whatsapp-agent/rules.py` is the single cached
loader for 6 JSON config files (§5). Pricing de-duplicated to one source. The
Laundry Class agent has its own file KB (`config/laundrykhalaas_knowledge.json` +
`laundry_class/knowledge_base.py`) with official prices. The dashboard's copy/
section labels live in `apps/admin/lib/dashboard/sections.ts`.

## 9. Global Filter Status

Centralized and **functional**, not visual-only. A React Context filter store +
controlled `FilterBar` (Date/Market/Region/City/Channel/Service) with active chips
and Clear all; pure filter engine in `apps/admin/lib/dashboard/filters.ts`. Tables,
lists and categorical charts re-slice live on Overview, Operations, Sales, Finance;
facility views stay PII-safe. Headline KPI trend cards / time-series remain period
snapshots by design. A reusable `LocalFilters` covers pages where global geo
doesn't apply. The custom `FilterSelect` is the single dropdown used by both the
global `FilterBar` and `LocalFilterBar` (no native `<select>`).

## 10. Known Limitations

- **Not a git repository** — no version control; changes are unversioned. Docs are
  the only history.
- Everything is **mock** (see §11). No live WhatsApp/Stripe/LLM/DB.
- **Two backends** (legacy `app/` :8000 vs active `apps/whatsapp-agent/` :8100);
  Classifier lives only in the legacy one and is not wired into the active agent.
- Dashboard uses in-memory TS mock data; **not wired to the agent's order API**
  server-side (Operations console is the main live wiring).
- **Approvals are not persisted server-side** (approval workflow is UI/session).
- No **conversation inbox/list endpoint** on the standalone backend yet.
- Laundry Class TC9 estimate over-counts on item re-description.
- **Windows-only build quirk:** `next build` fails at the `500.html` rename step
  even though it compiles fine; verify via `tsc --noEmit` + dev/Playwright, and
  never run `next build` while a dev server is up. Use `LK_DIST_DIR` for isolated
  builds.

## 11. Current Mock / Live Status

| Capability | Status |
|---|---|
| WhatsApp | **Mock** (MockWhatsAppAdapter; Meta Cloud API is a stub) |
| LLM | **Mock** (deterministic; Anthropic/OpenAI providers are stubs) |
| Stripe / Payments | **Mock / off** |
| Database (active agent) | **SQLite local mock** |
| Database (planned) | Postgres/pgvector/PostGIS (not active) |
| Dashboard data | **In-memory TS mock** |
| Drivers / Facility / Customer app | **Mock / not built** |
| Secrets | None committed; `.env` local only, `.env.example` safe |

No live external calls anywhere without explicit approval (`CLAUDE.md` §5).

## 12. Next Recommended Build Step

Per the roadmap (`CLAUDE.md` §18) and the current IA direction, the highest-value
next steps — **pending founder confirmation** — are:

1. **Dashboard subsection architecture across all sections** (finish the
   landing-page + subsection-cards pattern beyond Operations).
2. **Global filters applied across all sections/subsections/tabs** (ensure no
   remaining visual-only filters).
3. **Dashboard ↔ agent order API wiring** (replace in-memory mock order data on
   Operations/Customer Orders with the live :8100 order API).
4. **Server-side approval persistence** + a **conversation inbox/list endpoint**.
5. **Classifier scenario/evaluation pack**, then port the **Classifier Agent**
   into the standalone stack ahead of the WhatsApp agent.

Recommended first: **#3 (order API wiring)** or **#1 (subsection IA)** — both are
mock-safe, high-visibility, and unblock demos. Awaiting founder decision before
any coding.

---

## Tests Run

None — this was a read-only reconstruction. No code changed, so no build/test run
was warranted. (Existing state per docs: standalone agent 142 tests passing;
Laundry Class 13/13; dashboard typecheck clean, Playwright-verified.)

## Security / Privacy Notes

No secrets read or exposed. Privacy firewall and mock-only posture confirmed intact
across facility/driver views. No live integrations touched.

## Next Step

Await founder confirmation of the next task (see §12). Do not start coding until
confirmed.
