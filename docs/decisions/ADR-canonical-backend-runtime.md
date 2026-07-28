# ADR: Canonical Backend Runtime

**Status:** Accepted
**Date:** 2026-07-28
**Context:** The repo contained two backend/agent trees (root `app/` and
`apps/whatsapp-agent/`), risking two parallel agent implementations, two sets of
models, two API surfaces, two booking flows, and two sources of truth.

## Decision
**`apps/whatsapp-agent/` is the single canonical backend/runtime.**

- `apps/admin` (internal dashboard) and `apps/facility-dashboard` (partner
  dashboard) must call **only** this backend (`http://localhost:8100`, env-controlled).
- Root `app/` is **deprecated** — it was archived to `legacy/root-app/` during
  consolidation and then **removed from the tree** (2026-07-28); it is recoverable
  from git history only.
- **No new business logic** may reintroduce or extend the old root `app/`.
- All future agent, booking, order, pricing, discount, facility, notification, and
  LLM work happens in `apps/whatsapp-agent/`.
- The single database source of truth is **Supabase**, with migrations in root
  `supabase/migrations/`.
- Deployment/run commands use only the canonical backend.

## Rationale
The canonical backend owns all current live work: the Evolution WhatsApp webhook,
Supabase repositories + migrations, Claude/Anthropic tool-use integration, the
booking FSM, final VAT-inclusive pricing + discounts, message aggregation, facility
assignment/notifications, and the internal + facility dashboard APIs. The root `app/`
tree was an early mock-first prototype (SQLAlchemy/Alembic/Celery + a LangGraph
approval graph) that nothing outside itself imports. See
[`docs/audits/backend-consolidation-audit.md`](../audits/backend-consolidation-audit.md).

## Canonical run commands
```
# Backend (canonical) — port 8100
cd apps/whatsapp-agent
./.venv/Scripts/python.exe -m uvicorn main:app --host 0.0.0.0 --port 8100

# Internal dashboard — port 3005
cd apps/admin
npx next dev -p 3005

# Facility dashboard — port 3010
cd apps/facility-dashboard
npx next dev -p 3010
```

## Consequences
- One runtime, one API surface, one booking/order/pricing/facility path.
- The legacy `docker compose up` (:8000) stack is gone from the repo root; it was
  archived under `legacy/root-app/` and then removed (2026-07-28), recoverable from
  git history only.
- Any legacy LangGraph orchestration is **intentionally discarded** (not migrated)
  to avoid a second live implementation; its concepts already exist in the canonical
  backend (domain guard, escalation/human-takeover, approval flow).

## Non-goals
This decision is a consolidation only — it does not change agent behavior or add
features.
