# Supabase Dev/Test Database — Architecture

> **DEV/TEST ONLY. Not production.** A separate production Supabase project will
> be created later with its own auth/RLS/deployment design. No real customer
> data belongs in this project.

Related: [[test-data-strategy]], [[whatsapp-agent-dashboard-inbox]],
[[standalone-whatsapp-agent]], [[whatsapp-agent-architecture]],
[[privacy-firewall]], [[mock-order-lifecycle]].

## Purpose

A dedicated dev/test Supabase (Postgres) project for exercising the WhatsApp
Agent end-to-end: inbox conversations, human takeover, order lifecycle,
dashboard, flags, and scenario/regression testing — with seeded fake data.

## Architecture (non-negotiable)

```
Dashboard (apps/admin)  →  FastAPI (apps/whatsapp-agent)  →  Supabase Postgres
        │                            │                              │
   never talks to               owns all data access          RLS-protected;
   Supabase directly            (service role / DATABASE_URL)  backend bypasses
```

The dashboard performs **no** sensitive operation against Supabase directly. The
`SUPABASE_SERVICE_ROLE_KEY` and `DATABASE_URL` are **backend-only** and never
shipped to the frontend.

## Modes

The backend runs in one of two DB modes, selected by `DATABASE_MODE`:

| mode       | driver / store                     | when                        |
|------------|-------------------------------------|-----------------------------|
| `sqlite`   | SQLAlchemy + aiosqlite (`db/__init__.py`) | default / local / tests |
| `supabase` | asyncpg pool (`db/database.py`)     | dev/test Supabase project   |

`db/database.py::is_supabase_mode()` is the single switch. In `sqlite` mode the
existing chat + order flow is unchanged; the new inbox/flag endpoints return
empty lists (reads) or `503` (writes). In `supabase` mode those endpoints read
and write the Supabase schema via `db/repositories/*`.

## Schema (10 tables)

`customers`, `conversations`, `messages`, `orders`, `order_events`,
`agent_flags`, `human_takeovers`, `approval_queue`, `tickets`, `agent_logs`.

- UUID PKs (`gen_random_uuid()`), `timestamptz`, `jsonb` for metadata/payloads.
- `updated_at` maintained by a shared `set_updated_at()` trigger.
- Indexed on the columns the inbox/dashboard filter by (status, priority,
  human_intervention_required, conversation_id, last_message_at, seed_batch_id).
- Every business table carries the 7 test-data marker columns — see
  [[test-data-strategy]].

Defined in `supabase/migrations/20260721_000001_initial_whatsapp_agent_dev_schema.sql`.

## Repository layer (`apps/whatsapp-agent/db/`)

```
db/
  __init__.py            # SQLite ORM engine/session (unchanged local mode)
  database.py            # asyncpg pool, DSN normalization, json codecs, db_health()
  repositories/
    conversations_repo.py  # list/get, start-takeover, return-to-bot, resolve
    messages_repo.py       # list, add (human/agent/system)
    orders_repo.py         # active/completed/list/get/complete/set_status/metrics (OrderRead shape)
    flags_repo.py          # list, resolve
    human_takeovers_repo.py# start/end/active-for-conversation
```

`db.py` was converted to the `db/` package so the original
`from db import Base, get_db, init_db, AsyncSessionLocal` surface is unchanged
while `db.database` + `db.repositories` are added alongside.

## FastAPI endpoints

```
GET  /health/db                                        # mode + connectivity (no secrets)

GET  /api/conversations[?status=]                      # supabase; [] in sqlite mode
GET  /api/conversations/{id}
GET  /api/conversations/{id}/messages
POST /api/conversations/{id}/human-takeover
POST /api/conversations/{id}/return-to-bot
POST /api/conversations/{id}/human-message
POST /api/conversations/{id}/resolve

GET  /api/orders  /active  /completed  /metrics  /{id} # sqlite or supabase per mode
POST /api/orders/{id}/complete   POST /api/orders/{id}/status

GET  /api/flags[?status=]                              # supabase; [] in sqlite mode
POST /api/flags/{flag_id}/resolve
```

Write endpoints that require the rich schema return `503` in sqlite mode with a
clear message; the order endpoints work in both modes (mode branch).

## Row Level Security (dev/test posture)

RLS is **enabled on every table with no anon/authenticated policies** →
the public PostgREST API is denied by default. The backend connects with the
service role (direct Postgres) which bypasses RLS. This enforces "frontend must
go through FastAPI." Production will get a proper RLS/auth design in its own
project — intentionally **not** built here.

## What is NOT done here (deferred)

- Production Supabase project, secrets, policies, deployment.
- Wiring the agent's live chat write-path to Supabase (the legacy test-chat
  endpoint still targets the SQLite ORM; the inbox reads/writes Supabase).
- Live verification against the real project (pending `.env` credentials).
