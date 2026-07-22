# Fresh Project Start Report

This document records the review performed before starting the new
LaundryKhalas WhatsApp Operations Agent backend, and the scaffolding
decisions that followed from it.

## Prototype Review — D:\LaundryKhalas\LaundryKhalasPrototype

**Stack summary:** Next.js 14 (App Router) frontend with fully in-memory/mock
data, paired with a *real, already-functioning* FastAPI + PostgreSQL +
Celery + Redis backend under `backend/`. This is not a throwaway demo — it
is a prior, partially-built attempt at almost exactly the same thing this
new project intends to build (mock-first WhatsApp agent, approval queue, AI
action logging), just without LangGraph and without auth.

**CLAUDE.md summary:** The root `CLAUDE.md` documents the frontend file map,
data model, and routing conventions, but flags itself as stale — it still
says "no backend, no auth" even though a real backend now exists. It points
to `docs/00-Home.md` as the authoritative entry point and to
`docs/decisions/` (ADRs) as overriding raw spec text. The `docs/` tree (an
Obsidian vault) is unusually rich: it contains ADRs (`docs/decisions/ADR-001`
through `ADR-006`), a `docs/audits/week-1-gap-audit.md` that already
performed a KEEP/REFACTOR/REBUILD/REMOVE classification of this exact
codebase, a 90-day roadmap, and detailed architecture/security docs. Several
hard decisions (mock-first policy, LLM gateway rule, backend-auth-only) were
already reasoned through there and are consistent with this new project's
brief.

### 1. Folder structure

```
LaundryKhalasPrototype/
├── app/                  Next.js App Router (admin/, user/) — no app/api/**
├── components/           ui/ (shadcn primitives), admin/AdminLayout.tsx, user/UserLayout.tsx, shared/StatusBadge.tsx
├── lib/                  mock-data.ts, agents/ (client-side mock agent framework), app-context.tsx, unified-chat-service.ts
├── hooks/use-toast.ts
├── public/logo.png
├── docs/                 Obsidian vault: specs, ADRs, roadmap, architecture, security, audits, checklists
├── backend/              Separate Python/FastAPI project (see §2/§3)
├── docker-compose.yml, Dockerfile, netlify.toml, .vercel/, .railwayignore, deploy-railway.ps1
└── CLAUDE.md
```

`backend/` is a self-contained Python 3.11 project (`pyproject.toml`, its
own `docker-compose.yml`, `Dockerfile`, `railway.json`, `alembic/`, `tests/`)
with `app/{api,agents,channels,core,db,models,schemas,services,tasks}`. It is
real, not a stub — it has Alembic migrations, SQLAlchemy models, pytest
tests (19 files), and runs against real Postgres/Redis in Docker.

### 2. Frontend framework/stack

Next.js **14.2.13** (App Router, every page is `'use client'` — no server
components in practice), React **18**, TypeScript 5, Tailwind CSS 3.4 +
shadcn/ui (Radix primitives, confirmed by `components.json` — style
"default", baseColor "slate", aliases `@/components`, `@/lib/utils`). Charts
via Recharts, forms via React Hook Form + Zod. State management is plain
React Context (`lib/app-context.tsx` for orders/drivers,
`lib/agent-context.tsx` for conversations) — no Redux/Zustand. Routing is
purely file-based App Router with `/admin/*` and `/user/*` trees, each
wrapped in its own layout/shell.

### 3. Backend/API structure

**No `app/api/**` exists in the Next.js app** — confirmed by directory
listing (`app/` only contains `admin/`, `user/`, `layout.tsx`, `page.tsx`,
`globals.css`). All "backend" logic for the Next.js app is client-side mock
services (`lib/unified-chat-service.ts`, `lib/agents/*`).

The real backend lives in `backend/app/`:
- `api/health.py`, `verification.py`, `proto_orders.py`, `whatsapp.py`, `approvals.py`, `admin.py`, `booking.py`
- `admin.py` exposes `/admin/orders/today`, `/admin/conversations` (+ detail/urgent/reply/takeover), `/admin/approvals`, `/admin/ai-action-log`, `/admin/cost-tracking`, `/admin/markets` — all reading real Postgres rows, no frontend fixtures.
- `whatsapp.py` implements `/api/whatsapp/simulate-message`: privacy filter → classifier via `LLMService` (mock by default) → regex-based item parsing → hardcoded `ITEM_PRICING` dict → order creation into a `prototype_orders` JSONB bridge table.
- `approvals.py` implements a full approval-queue lifecycle: create/list/get/approve/reject, with `approve` being the *only* place an agent-drafted customer reply is actually sent via `MockWhatsAppAdapter`.
- Database is **real PostgreSQL 16 with pgvector**, via async SQLAlchemy 2.x + Alembic (4 migrations), not in-memory. `docker-compose.yml` (both root and `backend/`) wires Postgres, Redis, backend, Celery worker (+ beat in the backend-local compose), and Adminer.

### 4. Existing admin/dashboard screens

`app/admin/*` (20 routes): Dashboard, Orders + detail, Driver Dispatch,
Facilities, Agent Hub, Conversations, Escalations, Agent Logs, "WhatsApp
Intelligence" (`/admin/agent`), AI Command Center (`/admin/ai-command`),
Marketing Hub + Content Calendar, Customers, Business Clients, Memberships,
Approvals, Reports, Settings, Unified Chat, Intent Classifier. Per the
existing gap audit, only `app/user/agent/page.tsx` actually calls the real
backend (the WhatsApp simulate endpoint); every admin page still reads from
`lib/mock-data.ts`.

### 5. Existing conversation/chat/WhatsApp features

Two parallel implementations exist:
- **Frontend mock layer**: `lib/agents/types.ts` defines a `Conversation`/`Message` shape with `intent`, `sentiment`, status (`active|resolved|escalated|waiting_human`); `app/admin/conversations/page.tsx` is a full inbox UI — status tabs, search, message thread, manual reply box, and a "simulate incoming message" dev tool. `lib/agents/channel/whatsapp-adapter.ts` is a client-side mock adapter.
- **Real backend**: `backend/app/channels/mock_whatsapp.py` — a genuine `MockWhatsAppAdapter` that persists every inbound/outbound message as a real `messages` row (get-or-create customer/conversation, zero external calls, explicitly documented as such in its docstring), plus `backend/app/channels/meta_whatsapp_stub.py` as a placeholder for a future live Meta Cloud API adapter, and `backend/app/models/conversation.py` defining `Conversation`/`Message` ORM models with a `manual_takeover` boolean that gates whether the agent may draft/queue replies at all.

### 6. Existing order/customer/facility data concepts

Two competing shapes exist — frontend mock types vs. backend ORM models:

- **Frontend** (`lib/mock-data.ts`): `Order { id, customerId, customerName, customerPhone, services[], items[], pickupAddress, deliveryAddress, emirate, status (9 states), driverId, amount, paymentMethod, paymentStatus, isB2B, ... }`; `Customer { id, name, phone, email, emirate, savedAddresses[], ordersCount, status: active|vip|inactive, totalSpent }`; `Driver`, `BusinessClient`, `Service`, `AgentMessage`.
- **Backend** (`backend/app/models/order.py`): `Order` with UUID PKs, FKs to `markets`, `customers`, `customer_addresses`, `facilities`, `drivers`; a **24-state `OrderStatus` enum** including canonical states (`inquiry` → `created` → ... → `closed`) plus exception states (`escalated_to_human`, `disputed`, `refunded_partial/full`, `cancelled`) plus explicitly-labeled legacy states kept "for prototype backwards-compat". Status transitions are enforced by a **Postgres trigger**, not application code. `backend/app/models/facility.py`, `driver.py`, `customer.py`, `market.py`, `pricing.py`, `ticket.py`, `ai_log.py` round out the schema (10 tables total).

### 7. Existing mock/demo data

Clearly labeled as mock: `lib/mock-data.ts` opens with
`// Mock data for LaundryKhalas demo app` and phone numbers are already
partially redacted with `XXX` (e.g. `+971 50 XXX 5566`) — a
privacy-conscious habit worth keeping. `lib/unified-chat-service.ts` is a
fully hardcoded keyword-pattern responder (not an LLM call) that returns
canned metrics/tables for the AI Command Center demo — cosmetic, not a
working analytics pipeline. `backend/app/api/whatsapp.py` seeds a fixed
"demo market" UUID (`_DEMO_MARKET_ID`) and a hardcoded `ITEM_PRICING` dict —
real DB rows, but demo-shaped data; the existing gap audit already flags
this pricing bypass as a rule violation risk.

### 8. Existing deployment/config files

Two Docker Compose stacks (root, for combined deploy, and `backend/`,
standalone) both define `postgres` (pgvector image), `redis`, `backend`,
`celery_worker`, `adminer`; the backend-local one adds `celery_beat`. Root
`Dockerfile` builds the Python backend image; `netlify.toml` and
`.vercel/project.json` show the frontend was deployed to both Netlify and
Vercel at different points; `backend/railway.json` + `.railwayignore`
(excludes all frontend files) show the backend deploys separately to
Railway. `.env.example` exists at both root and `backend/`, listing (names
only): `APP_ENV`, `DEBUG`, `MOCK_LLM`, `POSTGRES_USER/PASSWORD/DB/HOST/PORT`,
`DATABASE_URL`, `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`,
`ANTHROPIC_API_KEY`, `ANTHROPIC_COMPLEX_MODEL`, `ANTHROPIC_ROUTINE_MODEL`,
`LLM_PER_MESSAGE_TOKEN_CAP`, `LLM_CONVERSATION_TOKEN_CEILING`,
`LLM_PER_CUSTOMER_DAILY_TOKEN_CAP`, `LLM_GLOBAL_DAILY_TOKEN_CAP`. Real
`.env`/`.env.local` files exist at root and in `backend/` (contents not
read, per instructions not to read secrets).

### 9. What can be reused (as reference, not copy-paste)

- **Mock-first channel pattern**: `MockWhatsAppAdapter` persists messages identically to a live channel with zero external calls, so downstream code (admin, agent, approvals) can't tell mock from live. This new project implements the same pattern (`app/channels/base.py` + `mock_whatsapp.py` + `meta_whatsapp_stub.py`).
- **Approval-gated agent replies**: the booking-agent → `HumanApproval` → approve-then-send flow is a clean, reusable *concept* for "agent drafts, human approves, only approval triggers send." Adopted directly in this project's approval flow.
- **Privacy filter**: a simple, testable regex-based phone/email redaction applied before any LLM prompt. Small, dependency-free, conceptually ported into `app/services/privacy.py`.
- **AIActionLog / cost-tracking concept**: every LLM call logged with tokens/cost/latency, surfaced via admin endpoints — replicated as `AIActionLog` + `CostTracking` models here.
- **UI concepts** (not code): conversation inbox layout, approval queue, manual-takeover toggle (see §13).
- Type shapes in `lib/mock-data.ts` and `backend/app/models/*` are useful as a checklist of fields real laundry/delivery ops need (pickup/delivery windows, area, B2B flag, facility assignment) even though the concrete TS interfaces and SQLAlchemy models are not copied verbatim.

### 10. What should be rebuilt

- **Agent orchestration**: the prototype's booking agent is a hand-rolled sequential tool-chain, documented in its own docstring as a placeholder for LangGraph. This new project builds the WhatsApp Operations Agent as a real LangGraph graph from the start.
- **Auth/RBAC**: entirely absent in the prototype backend — every endpoint takes no auth dependency. This new project adds a placeholder admin API-key check (`app/core/security.py`) on all admin routes from day one, to be replaced by real auth/RBAC before live launch.
- **Classifier prompt**: the prototype's classifier runs on an admitted placeholder prompt. Out of scope for this task by explicit instruction — deferred to the classifier-agent task.
- **CORS policy**: prototype uses `allow_origins=["*"]`. This new project keeps CORS narrow/config-driven and documents it as a pre-live checklist item.
- **Pricing sourcing**: the prototype's WhatsApp demo path hardcodes a pricing dict instead of reading a pricing table. This new project's `get_retail_price` tool reads only from `CountryConfig.pricing_config_json`, never invents a number.

### 11. What should be ignored/discarded

- `lib/unified-chat-service.ts` — a fully scripted keyword-matcher masquerading as an "AI Command Center"; useful only as an example of what not to build (canned responses, fake confidence scores).
- The dual-deployment history (Netlify **and** Vercel configs, `.bolt/` AI-website-builder config, `deploy-railway.ps1`) — platform churn, not relevant to a fresh Python backend.
- `backend/DELIVERY_NOTES.md` — flagged by the prototype's own gap audit as possibly stale; not treated as current truth.
- Legacy `OrderStatus` values kept "for prototype backwards compat" (`confirmed`, `pickup_assigned`, `cleaning`, etc.) — vestigial, not carried into this project's 10-state machine.
- Two nearly-identical `docker-compose.yml` files (root vs. `backend/`) reflect an unresolved "is this one project or two" tension — this new project picks one topology (single `docker-compose.yml` at root) from the start.

### 12. Risks found

- **No authentication/authorization anywhere in the prototype FastAPI backend.** Every route in `admin.py`, `approvals.py`, `whatsapp.py`, `booking.py`, `proto_orders.py` is open — no route declares an auth dependency. Independently flagged as Critical Risk #1 in the prototype's own `docs/audits/week-1-gap-audit.md`. **Mitigation in this project:** every `/api/admin/**` route requires `X-Admin-Api-Key` via `app/core/security.py::require_admin` (placeholder-strength, but non-optional; a real RBAC system is required before live launch — see `docs/checklists/live-whatsapp-readiness.md`).
- **CORS wildcard** (`allow_origins=["*"]`, `allow_credentials=False`) in the prototype backend. Not exploitable there only because nothing is protected and credentials are off; would become dangerous the moment auth is added without tightening CORS in lockstep. This project ships without a wildcard CORS default (see `app/main.py`).
- **Hardcoded default DB credentials** in prototype source (`POSTGRES_PASSWORD: laundrykhalas_dev` in both compose files and as a `Settings` default). Low real risk (dev-only) but a bad habit. This project uses an equally-fake but clearly-named `changeme_local_only` default and documents it as dev-only.
- **No hardcoded API keys or live secrets found** in the prototype — a targeted review found no Anthropic/OpenAI/AWS key patterns or bearer-token literals. `ANTHROPIC_API_KEY` defaults empty; mock LLM is the default. Nothing was carried into this project regardless.
- **`.env`/`.env.local` exist in prototype root and `backend/`** — contents were not read. Not copied into this project; this project ships only `.env.example` with names, no values.
- **No live external API calls found** in the reviewed prototype code paths — consistent with a mock-first policy this project also follows.

### 13. Useful UI/UX ideas worth carrying forward (for the future admin dashboard, not built in this task)

- **Conversation inbox layout**: status-tab filtering (All/Active/Escalated/Waiting/Resolved), searchable list on the left, full thread + reply composer on the right, and an inline "simulate incoming message" tool for testing without a real channel.
- **Manual-takeover toggle**: a single boolean per conversation that silences the agent's customer-facing replies while leaving order-side automation untouched — this project's `Conversation.manual_takeover` field implements exactly this.
- **Approval queue as its own first-class surface**: urgency-sorted queue, action-type tagging, and the rule that approving a `send_customer_reply` action is the only path that actually sends it — this project's `/api/admin/approvals` implements this rule.
- **AI action log / cost tracking as a visible admin page**, not just background logging — this project's `/api/admin/ai-action-logs` implements this.
- **Order status pipeline as a visual list of states with badges** — a UI idea for the future dashboard; this project's backend exposes `status` plainly so a future frontend can map it to badges.
- **Sidebar grouped by function** (Operations / Agents / Escalations / Workflow) — a reasonable information architecture starting point for a future admin dashboard.

### Conclusion

The prototype (including its `backend/` folder) is genuinely useful reference
material — several architectural instincts (mock adapter pattern,
approval-gated replies, audit logging, DB-sourced pricing) are directionally
correct and were carried forward *as concepts*. No code, secrets, or demo
data were copied. The most important gap to close relative to the prototype
is authentication on admin routes, which this project addresses immediately
rather than deferring. The prototype remains reference material only; this
new project is the sole source of truth going forward.
