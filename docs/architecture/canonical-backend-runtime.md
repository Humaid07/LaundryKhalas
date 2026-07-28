# Canonical Backend Runtime

The single backend/runtime for LaundryKhalas is **`apps/whatsapp-agent/`**
(FastAPI + Supabase/asyncpg + Evolution WhatsApp + Claude tool-use). Decision:
[`ADR-canonical-backend-runtime`](../decisions/ADR-canonical-backend-runtime.md).

## What it owns
WhatsApp agent runtime · Evolution webhook (`POST /webhooks/evolution`) · booking
FSM · order lifecycle · pricing (VAT-inclusive) · discounts · facility assignment ·
facility notifications · facility dashboard APIs · internal dashboard APIs ·
Claude/LLM integration · Supabase repositories · migrations (`supabase/migrations/`) ·
backend tests · deployment.

## Run commands
```
# Backend — port 8100 (must match the Evolution webhook target)
cd apps/whatsapp-agent
./.venv/Scripts/python.exe -m uvicorn main:app --host 0.0.0.0 --port 8100

# Internal dashboard — port 3005
cd apps/admin
npx next dev -p 3005

# Facility dashboard — port 3010
cd apps/facility-dashboard
npx next dev -p 3010
```

## Tests
```
cd apps/whatsapp-agent
./.venv/Scripts/python.exe -m pytest -q          # full suite (~large; run targeted files when iterating)
./.venv/Scripts/python.exe -m ruff check .
```

## Config / secrets
- Backend config: `apps/whatsapp-agent/.env` (gitignored). `ANTHROPIC_API_KEY`,
  `AI_PROVIDER`/`LLM_PROVIDER`, `ANTHROPIC_ENABLED`, Evolution + Supabase settings.
- Dashboards read the backend base URL from env (`NEXT_PUBLIC_API_BASE_URL`),
  default `http://localhost:8100`.
- DB: Supabase (remote). Migrations in root `supabase/migrations/`, applied via
  asyncpg (apply `.sql` manually — no generic runner).

## Health / smoke
- `GET /health` and `GET /health/ai` on :8100.
- Evolution route: `POST /webhooks/evolution`.
- Admin loads orders/conversations; facility dashboard loads overview/orders — both
  against :8100.

## Do not
- Run or extend `legacy/root-app/` (the archived :8000 prototype).
- Add a third backend structure.
- Give a dashboard direct Supabase access (it must go through the backend API).
