# Build Report — Supabase Dev/Test Database for the WhatsApp Agent

**Date:** 2026-07-21
**Area:** `supabase/`, `apps/whatsapp-agent/`, `apps/admin/`
**Status:** schema + seed + scripts + backend + dashboard client + docs done;
**live Supabase verification pending credentials.**

## 1. Objective

Set up the current (separate) Supabase project as the LaundryKhalas **DEV/TEST**
database for WhatsApp Agent / inbox / human-takeover / order-lifecycle / dashboard
/ scenario testing. Keep the architecture Dashboard → FastAPI → Supabase; no live
WhatsApp/Stripe/LLM; no real data; no production Supabase yet.

## 2. What changed because this is a dev/test project

- Seeding demo WhatsApp data into this project is intentional and supported.
- Reset/delete of test data is supported via a guarded script.
- Seed/reset scripts are gated on `APP_ENV`, `DATABASE_ENV`,
  `SUPABASE_PROJECT_TYPE`, `DATABASE_MODE`, and `ALLOW_TEST_*`.
- Every seeded row is marked test/demo (7 marker columns).
- No production policies/secrets/deployment; production project is deferred.

## 3. Supabase files created

- `supabase/migrations/20260721_000001_initial_whatsapp_agent_dev_schema.sql`
- `supabase/migrations/20260721_000002_seed_whatsapp_agent_test_data.sql`
- `supabase/README.md`

## 4. Tables / migrations

10 tables (UUID PKs, `timestamptz`, `jsonb`, indexes, `updated_at` triggers, RLS
enabled): `customers`, `conversations`, `messages`, `orders`, `order_events`,
`agent_flags`, `human_takeovers`, `approval_queue`, `tickets`, `agent_logs`.

## 5. Test-data fields added (every business table)

`is_test_data`, `is_demo`, `environment`, `seed_batch_id`, `seed_source`,
`test_scenario_id`, `created_by_seed`.

## 6. Seed data

Fixed-UUID, idempotent (`on conflict do nothing`), all marked test/demo with
`seed_batch_id='20260721_whatsapp_agent_seed_v1'`,
`seed_source='whatsapp_agent_test_seed'`:
6 customers, 6 conversations (booking, refund-urgent, damaged, track, B2B,
payment), 18 messages, 5 orders (`LK-AE-1024/1025/1026/1027/2031`), 5 agent
flags, 2 human takeovers, 3 tickets, 2 approvals, 3 order events, 4 agent logs.
The refund conversation is `human_intervention_required=true`, `priority=urgent`,
`flag_type=refund_request`, team `Customer Facing / Finance`, with the exact
suggested reply *"Please hold on while we find a quick solution. Our team will get
back to you shortly."*

## 7. Scenario fixture files

`apps/whatsapp-agent/test-data/scenarios/` — 9 files, **37 scenarios**:
`booking_flow` (5), `refund` (4), `complaint` (4), `damaged_item` (4),
`missing_item` (4), `payment_issue` (4), `b2b` (4), `out_of_domain` (4),
`prompt_injection` (4). Each scenario carries the 12 required fields
(scenario_id, category, customer_message, expected_intent/sentiment/urgency,
expected_human_intervention_required, expected_dashboard_flag,
expected_short_reply, linked_demo_order_id, expected_team_routing,
forbidden_actions). No invented prices/refunds/policies.

## 8. Seed/reset safety checks

- `scripts/_safety.py` — pure guard functions + FK-safe delete order.
- `scripts/verify_supabase_connection.py` — read-only connectivity + table/seed
  counts.
- `scripts/seed_supabase_test_data.py` — refuses unless dev/test + `ALLOW_TEST_SEED`;
  executes the seed migration (idempotent).
- `scripts/reset_supabase_test_data.py` — refuses unless dev/test +
  `ALLOW_TEST_RESET`; deletes only `is_test_data AND created_by_seed` rows,
  child-before-parent, never truncates, never touches non-test rows.
- Production abort message honored exactly.

## 9. FastAPI changes

- `db.py` → `db/` package: `db/__init__.py` (unchanged SQLite ORM surface),
  `db/database.py` (asyncpg pool, DSN normalization, json codecs, `db_health()`,
  `is_supabase_mode()`), `db/repositories/*` (conversations, messages, orders,
  flags, human_takeovers).
- New routers: `api/conversations.py`, `api/flags.py`, `api/health.py`
  (`/health/db`). `api/orders.py` now branches to Supabase in supabase mode.
- `main.py` registers the new routers and **skips** SQLite ORM init/seed in
  supabase mode (schema/seed are migration-owned); closes the pool on shutdown.
- `settings.py`: added `database_env`, `database_mode`, `supabase_project_type`,
  `allow_test_seed`, `allow_test_reset`, `supabase_url`, `supabase_anon_key`,
  `supabase_service_role_key`.
- `schemas.py`: `HumanTakeoverRequest`, `HumanMessageRequest`, `DbHealth`.

Endpoints: `/health/db`; `/api/conversations` (+`/{id}`, `/{id}/messages`,
`/human-takeover`, `/return-to-bot`, `/human-message`, `/resolve`); `/api/orders`
(+`/active`, `/completed`, `/metrics`, `/{id}`, `/{id}/complete`, `/{id}/status`);
`/api/flags` (+`/{id}/resolve`).

## 10. Dashboard API changes

`apps/admin/lib/dashboard/whatsapp-agent-api.ts`: added DTO types
(`DbHealth`, `InboxConversationDTO`, `InboxMessageDTO`, `AgentFlagDTO`,
`OrderDTO`) and methods `dbHealth`, `listConversations`, `getConversation`,
`getMessages`, `startHumanTakeover`, `returnToBot`, `sendHumanMessage`,
`resolveConversation`, `listFlags`, `resolveFlag`, `listOrders`,
`listActiveOrders`, `listCompletedOrders`, `getOrder`. The inbox now renders
**Test Data** / **Demo Conversation** badges from `is_test_data`/`is_demo`.

## 11. Env vars added to .env.example

`apps/whatsapp-agent/.env.example`: `DATABASE_ENV`, `DATABASE_MODE`,
`SUPABASE_PROJECT_TYPE`, `ALLOW_TEST_SEED`, `ALLOW_TEST_RESET`, `SUPABASE_URL`,
`SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, plus Supabase guidance on
`DATABASE_URL`. Defaults are safe (`DATABASE_MODE=sqlite`, `ALLOW_TEST_*=false`).
The service role key is documented as backend-only.

## 12. Tests / checks run

- `pytest` (apps/whatsapp-agent): **155 passed** (95 pre-existing + new guard/
  endpoint tests; the `db/` package conversion broke nothing).
- `ruff check` on new backend code: **clean**.
- Guard smoke test: seed/reset **refuse** correctly in sqlite mode; verify
  prints SKIP.
- `tsc --noEmit` (apps/admin): **0 errors** (repo-wide).
- Playwright: inbox renders **Test Data** + **Demo Conversation** badges, 0 page
  errors.

## 13. Supabase verification status

**Verified live (2026-07-21)** against the dev/test project
`inutjbnmyvfjijvbudun` (region **ap-southeast-2**, PostgreSQL 17.6) via the
**Session pooler** (`aws-0-ap-southeast-2.pooler.supabase.com:5432`, user
`postgres.<ref>`) — the direct `db.<ref>.supabase.co` host is IPv6-only and does
not resolve on IPv4, so the pooler is required. End-to-end confirmed:

- `verify_supabase_connection.py` → connected, all 10 tables present.
- `seed_supabase_test_data.py` → 54 rows (6 customers, 6 conversations, 18
  messages, 5 orders, 5 flags, 2 takeovers, 3 tickets, 2 approvals, 3 order
  events, 4 logs); **idempotent** (2nd run added 0).
- API (backend in supabase mode): `/health/db` connected; `/api/conversations`
  → 6 with **masked phones**; `/api/orders/active` → 4; `/api/flags?status=open`
  → 4 with correct team routing.
- Write path: human-takeover → human-message (stored, `is_test_data=false`) →
  return-to-bot → flag resolve — all 200.
- `reset_supabase_test_data.py` → deleted exactly the 54 seeded rows (runtime
  rows cascade-cleaned via FK); non-test rows untouched. Re-seed restored state.

Two bugs were found and fixed during the live run (commits `85b07ec`,
`<seed-path-fix>`): the ORM engine crashed on a bare `postgresql://` URL
(psycopg2 not installed) → now mapped to asyncpg; tests pinned to sqlite; and the
seed script's SQL path was off by one directory level.

## 14. Security / privacy

- Service role key + `DATABASE_URL` are backend-only; never sent to the frontend.
- RLS enabled on all tables (deny-by-default for anon); backend bypasses via
  service role. Dashboard → FastAPI only.
- Seed phones are obviously fake + masked; no full addresses; no PII.
- `.env` is gitignored; no secrets committed (verified pre-commit).

## 15. Known limitations

- Live Supabase now **verified** (see §13). Requires the Session pooler on IPv4.
- The agent's live chat write-path still targets the SQLite ORM; the inbox
  reads/writes Supabase. Unifying them is a follow-up.
- The dashboard inbox still renders seeded frontend data with badges; switching
  it to fetch from `/api/conversations` is prepared (client methods) but not
  wired, pending live Supabase.
- `next build` on this Windows box fails at the 500.html rename step (unrelated;
  verify via `tsc` + dev/Playwright — see [[project_2026-07-21_filterselect-and-build-quirk]]).

## 16. Recommended next step

Fill `apps/whatsapp-agent/.env` with the dev/test `DATABASE_URL` + keys, run
`supabase db push`, then `verify` → `seed`, and switch the dashboard inbox to
`agentApi.listConversations()` behind a "live inbox" flag.
