# Legacy root `app/` backend — ARCHIVED (reference only)

**This folder is archived legacy / reference code. Do NOT add new logic here and do NOT run it as a backend.**

The canonical LaundryKhalas backend/runtime is **`apps/whatsapp-agent/`**. See
[`docs/decisions/ADR-canonical-backend-runtime.md`](../../docs/decisions/ADR-canonical-backend-runtime.md)
and [`docs/architecture/canonical-backend-runtime.md`](../../docs/architecture/canonical-backend-runtime.md).

## What this was
An early mock-first prototype backend (FastAPI + SQLAlchemy/Alembic + Celery/Redis +
a LangGraph approval-workflow graph) that ran on **port 8000** via Docker Compose.
It was superseded by `apps/whatsapp-agent/` (FastAPI + Supabase/asyncpg + Evolution
WhatsApp + Claude tool-use orchestration) which carries all current live work.

## Why it was archived (2026-07-28)
The repo had two parallel backend trees, risking two agent implementations, two sets
of models, two API surfaces, two booking flows, and two sources of truth. Consolidation
made `apps/whatsapp-agent/` the single canonical runtime and moved this legacy stack
here, intact, for reference. Nothing outside this folder imports it.

## Contents (moved verbatim from the repo root)
- `app/` — legacy FastAPI app, agents (classifier + whatsapp_operations LangGraph graph), api/routes, models, schemas, services, db, tasks, tests
- `alembic/` + `alembic.ini` — legacy Postgres migrations (superseded by root `supabase/migrations/`)
- `docker-compose.yml` + `Dockerfile` + `docker/postgres.Dockerfile` — legacy container stack (Postgres + Redis + Celery + `app.main:app` on :8000; its `admin` service pointed at the old :8000 backend)
- `pyproject.toml` — legacy package deps (SQLAlchemy/Alembic/Celery/Redis/langgraph 0.1)
- `scripts/` — `seed_mock_data.py` (imports `app.`), `init_extensions.sql`

## If you ever need to run it (not recommended)
It is self-contained: from **inside this folder**, `docker compose up` still builds
`app.main:app`. Its `from app.` imports resolve because `app/` lives here alongside it.
This is for historical reference only — it is NOT part of the product runtime.

## Do not
- Add features here.
- Point any dashboard or script at it.
- Treat it as a second backend.
