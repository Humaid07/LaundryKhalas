# Backend Consolidation Audit

**Date:** 2026-07-28
**Purpose:** Eliminate the risk of two parallel agent/backend implementations by
identifying the canonical runtime and confirming the legacy tree can be safely
archived.

## TL;DR
The repo had **two** backend trees. `apps/whatsapp-agent/` is the canonical,
live, actively-developed backend. Root `app/` was an early prototype (superseded)
that **nothing outside itself imports**. It (plus its Alembic/Docker/Celery
tooling) was archived to `legacy/root-app/`.

## Runtime ownership

| Question | Answer |
|---|---|
| Which backend runs on **:8100** | `apps/whatsapp-agent/` (`uvicorn main:app`, via its own `.venv`) — the canonical runtime |
| Which backend the legacy Docker stack ran (**:8000**) | root `app/` (`uvicorn app.main:app` in `docker-compose.yml`) — legacy |
| Which backend **dashboards call** | `apps/admin` and `apps/facility-dashboard` call the canonical backend (`http://localhost:8100`, env-controlled). ⚠️ The legacy `docker-compose.yml` `admin` service pointed `NEXT_PUBLIC_API_BASE_URL` at `http://localhost:8000` (the old backend) — a footgun removed by archiving |
| Which backend **Evolution** calls | `POST /webhooks/evolution` in `apps/whatsapp-agent/api/evolution_webhooks.py` (canonical). Legacy `app/` only had a `mock_whatsapp` route |
| Which backend owns **Supabase repositories** | `apps/whatsapp-agent/db/repositories/*` (asyncpg). Legacy `app/db` used SQLAlchemy/Alembic against local Postgres |
| Which backend owns **booking/order/pricing/facility** logic | `apps/whatsapp-agent/services/*` + `agents/whatsapp_agent/*` (canonical) |
| Where **migrations** live (source of truth) | root **`supabase/migrations/`** (000001–000028, applied via asyncpg). Legacy `alembic/` is superseded |

## Reference search results

- `from app.` / `import app.` **outside** `app/`: only **2** files — `alembic/env.py`
  and `scripts/seed_mock_data.py` (both legacy tooling; both moved into the archive
  with `app/`, so their imports still resolve inside `legacy/root-app/`).
- **No** file in `apps/whatsapp-agent`, `apps/admin`, or `apps/facility-dashboard`
  imports root `app/`.
- Runtime refs to `app.main` / `app.tasks`: only root `docker-compose.yml` (3 lines)
  and root `Dockerfile` — the legacy stack. All archived.
- `.github/workflows`: none.
- Canonical backend uses **no** celery / redis / alembic (confirmed) — it is
  self-contained (Supabase + asyncpg + its own `pyproject.toml` + Dockerfile).

## Capability comparison

| Capability | Root `app/` (legacy) | `apps/whatsapp-agent` (canonical) | Decision |
|---|---|---|---|
| WhatsApp webhook | mock only (`mock_whatsapp` route) | **Evolution `POST /webhooks/evolution`** (live) | canonical |
| Evolution adapter | — | **`channels/evolution_whatsapp.py`** | canonical |
| Meta adapter | — | placeholder mode | canonical |
| Booking FSM | partial | **`services/booking_flow.py`** (persisted FSM) | canonical |
| Claude / Anthropic | early stub | **tool-use orchestration** (`agents/whatsapp_agent/booking_tools.py`, live) | canonical |
| LangGraph graph | `app/agents/whatsapp_operations/graph.py` (approval-workflow StateGraph) | `laundry_class/` LangGraph agent + Claude tool-use (production) | canonical; legacy graph **intentionally discarded** (see below) |
| Pricing engine | basic | **`services/pricing.py` + `money.py`** (VAT-inclusive, Decimal) | canonical |
| Discount engine | — | **`services/discount.py`** (15%/20% tiers, snapshotted) | canonical |
| Message aggregation | — | **`services/turn_service.py` + `message_aggregation.py`** | canonical |
| Order repository | SQLAlchemy models | **asyncpg `db/repositories/orders_repo.py`** | canonical |
| Supabase support | — | **full** (`db/`, `supabase/migrations/`) | canonical |
| Facility dashboard API | — | **`api/facility.py`** + repos | canonical |
| Facility assignment | — | **`services/facility_routing.py`** | canonical |
| Facility notifications | — | **`services/facility_notifications.py`** | canonical |
| Internal dashboard API | early routes | **`api/*`** (orders, conversations, metrics, users) | canonical |
| Auth / RBAC | — | **JWT + PBKDF2, RLS** (migration 000008) | canonical |
| Tests | `app/tests` (legacy) | **`apps/whatsapp-agent/tests/`** (700+) | canonical |
| Deployment path | `docker compose` (:8000) | venv `uvicorn main:app` :8100 (+ own Dockerfile) | canonical |

## LangGraph decision (Step 3/4)
`app/agents/whatsapp_operations/graph.py` is a legacy **approval-workflow**
`StateGraph` (load context → assemble safe context → decide action → tool loop →
safety filter → draft reply → create approval). It is **intentionally discarded**,
not migrated, because:
- The canonical production path is a mature, live Claude **tool-use** orchestration
  + deterministic FSM that supersedes it; migrating the graph would re-introduce a
  second parallel implementation (the exact risk this task removes).
- The canonical backend already ships its own LangGraph agent (`laundry_class/`,
  `langgraph>=0.2.0`) for its separate use case.
- The legacy graph's *concepts* (safety filter, human approval before send) already
  exist in the canonical backend as the domain guard, escalation/human-takeover, and
  the (MVP) approval flow.
The legacy graph was archived (and later removed with the rest of `legacy/root-app/`,
2026-07-28); it remains readable in git history at
`legacy/root-app/app/agents/whatsapp_operations/graph.py` for reference.

## Outcome
- Canonical runtime: **`apps/whatsapp-agent/`**.
- Legacy stack archived to `legacy/root-app/`, then **removed from the tree**
  (2026-07-28, owner-approved) — recoverable from git history only.
- Single DB source of truth: root `supabase/migrations/`.
- No remaining runnable second backend; no dashboard depends on `app/`.
