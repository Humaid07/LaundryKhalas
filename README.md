# LaundryKhalas

A laundry & cleaning marketplace with a WhatsApp-first customer experience, an
internal operations dashboard, and a partner/facility dashboard.

## Repository layout

| Path | What it is |
|---|---|
| **`apps/whatsapp-agent/`** | ★ **Canonical backend/runtime** (FastAPI + Supabase/asyncpg + Evolution WhatsApp + Claude tool-use). Owns the WhatsApp agent, booking/order/pricing/discount/facility/notification logic, LLM integration, Supabase repositories, and backend tests. Runs on **:8100**. |
| `apps/admin/` | Internal LaundryKhalas dashboard (Next.js). Calls the canonical backend. Runs on **:3005**. |
| `apps/facility-dashboard/` | Partner/facility dashboard (Next.js). Calls the canonical backend. Runs on **:3010**. |
| `supabase/migrations/` | Single database source of truth (applied via asyncpg). |
| `docs/` | Audits, decisions (ADRs), architecture, build reports, checklists. |
| `legacy/root-app/` | ⛔ Archived legacy prototype backend (old `:8000` Docker stack). Reference only — do not run or edit. |

See [`docs/architecture/repo-structure.md`](docs/architecture/repo-structure.md) and
[`docs/decisions/ADR-canonical-backend-runtime.md`](docs/decisions/ADR-canonical-backend-runtime.md).

## Run (local dev)

```bash
# Canonical backend — port 8100 (must match the Evolution webhook target)
cd apps/whatsapp-agent
cp .env.example .env          # then set ANTHROPIC_API_KEY, Evolution + Supabase vars (never commit .env)
./.venv/Scripts/python.exe -m uvicorn main:app --host 0.0.0.0 --port 8100

# Internal dashboard — port 3005
cd apps/admin && npx next dev -p 3005

# Facility dashboard — port 3010
cd apps/facility-dashboard && npx next dev -p 3010
```

Health: `GET http://localhost:8100/health` (and `/health/ai`). Evolution webhook:
`POST http://localhost:8100/webhooks/evolution`.

## Tests

```bash
cd apps/whatsapp-agent
./.venv/Scripts/python.exe -m pytest -q       # backend (large — run targeted files when iterating)
./.venv/Scripts/python.exe -m ruff check .
```

## Configuration

- Backend config lives in `apps/whatsapp-agent/.env` (gitignored). Keep all secrets
  there — never in git, never in chat.
- Dashboards read the backend base URL from `NEXT_PUBLIC_API_BASE_URL` (default
  `http://localhost:8100`).
- Database changes go through `supabase/migrations/` (apply `.sql` via asyncpg — no
  generic runner).

## Legacy

The original mock-first prototype backend (FastAPI + SQLAlchemy/Alembic + Celery,
`docker compose` on :8000) is archived under `legacy/root-app/` for reference. It is
not part of the runtime; see its README before touching it.
