# Supabase — LaundryKhalas WhatsApp Agent (DEV/TEST)

This folder holds the SQL schema and seed for the **separate dev/test Supabase
project** used for WhatsApp Agent / inbox / order-lifecycle / dashboard testing.

> ⚠️ **DEV/TEST ONLY — this is NOT production.** A separate production Supabase
> project will be created later with its own auth/RLS design. No real customer
> data belongs here. Every seeded row is marked test/demo.

## Layout

```
supabase/
  migrations/
    20260721_000001_initial_whatsapp_agent_dev_schema.sql   # 10 tables + indexes + RLS
    20260721_000002_seed_whatsapp_agent_test_data.sql        # fake/demo seed (idempotent)
  README.md
```

## Architecture

```
Dashboard (apps/admin) → FastAPI (apps/whatsapp-agent) → Supabase Postgres
```

The dashboard never talks to Supabase directly. The backend owns data access
using the service role over a direct Postgres connection (`DATABASE_URL`).

## Apply the schema

Option A — Supabase CLI (recommended):

```bash
supabase link --project-ref <dev-test-ref>
supabase db push            # applies migrations in order
```

Option B — run the SQL directly (e.g. Supabase SQL editor or psql) in order:
`000001` (schema) then `000002` (seed).

### Connection note (IPv4 networks)

The **direct** DB host `db.<ref>.supabase.co` is **IPv6-only** and will fail with
`getaddrinfo failed` on IPv4-only networks. Use the **Session pooler**
(Dashboard → Connect → Session pooler), which is IPv4-friendly and works with
asyncpg on port 5432:

```
postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres
```

(Note the username is `postgres.<ref>`, not `postgres`.) After a **Reset database
password**, the pooler can take up to ~1–2 minutes to propagate the new
credential before it authenticates.

## Seed / reset from the backend (guarded)

From `apps/whatsapp-agent` with `.env` set to the dev/test project
(`DATABASE_MODE=supabase`, `DATABASE_ENV=test`, `SUPABASE_PROJECT_TYPE=test`,
`ALLOW_TEST_SEED=true` / `ALLOW_TEST_RESET=true`):

```bash
python scripts/verify_supabase_connection.py   # read-only connectivity check
python scripts/seed_supabase_test_data.py       # idempotent; runs migration 000002
python scripts/reset_supabase_test_data.py       # deletes ONLY seeded test rows
```

The scripts refuse to run unless the environment is unambiguously dev/test, and
the reset only deletes rows where `is_test_data = true AND created_by_seed =
true`. They never touch non-test rows and never truncate.

## Test-data markers

Every business table carries: `is_test_data`, `is_demo`, `environment`,
`seed_batch_id`, `seed_source`, `test_scenario_id`, `created_by_seed`. Seeded
rows use `seed_batch_id = '20260721_whatsapp_agent_seed_v1'` and
`seed_source = 'whatsapp_agent_test_seed'`. See
[`docs/architecture/test-data-strategy.md`](../docs/architecture/test-data-strategy.md).

## RLS

RLS is enabled on every table with **no** anon/authenticated policies, so the
public PostgREST surface is denied by default. The backend service role bypasses
RLS. Production RLS/auth is designed later in the production project. See
[`docs/architecture/supabase-dev-database.md`](../docs/architecture/supabase-dev-database.md).
