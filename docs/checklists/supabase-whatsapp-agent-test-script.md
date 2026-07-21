# Supabase Dev/Test — WhatsApp Agent Test Script

Verifies the dev/test Supabase setup end-to-end. Some steps need Supabase
credentials in `.env`; where creds are absent, the SQLite-mode and guard steps
still fully verify the safety behaviour.

## 0. Prereqs

- `apps/whatsapp-agent/.env` copied from `.env.example`.
- For Supabase steps: `DATABASE_MODE=supabase`, `DATABASE_ENV=test`,
  `SUPABASE_PROJECT_TYPE=test`, a dev/test `DATABASE_URL`, and
  `ALLOW_TEST_SEED=true` / `ALLOW_TEST_RESET=true`.

## 1. Backend regression (SQLite mode — no creds needed)

```bash
cd apps/whatsapp-agent
.venv/Scripts/python.exe -m pytest -q
```
- [ ] All tests pass (155+), including `tests/test_supabase_safety.py`.

## 2. Safety guards (no creds needed)

With `DATABASE_MODE=sqlite` (or any non-dev/test value):
```bash
python scripts/seed_supabase_test_data.py      # must REFUSE
python scripts/reset_supabase_test_data.py     # must REFUSE
```
- [ ] Both print a refusal listing the failed gate and exit non-zero.
- [ ] Setting `APP_ENV=production` yields exactly:
      "Refusing to seed test data into production environment."

## 3. Health endpoint (SQLite mode)

```bash
uvicorn main:app --port 8100        # (or the project's run command)
curl localhost:8100/health/db
```
- [ ] Returns `{"status":"ok","mode":"sqlite","backend":"sqlite",...}`.
- [ ] `curl localhost:8100/api/conversations` → `[]`.
- [ ] `curl localhost:8100/api/flags` → `[]`.
- [ ] `curl -X POST localhost:8100/api/conversations/x/human-takeover` → 503.

## 4. Apply schema to dev/test Supabase (creds needed)

```bash
supabase link --project-ref <dev-test-ref>
supabase db push
```
- [ ] Migrations `000001` (schema) + `000002` (seed) apply without error.
- [ ] In the Supabase dashboard, all 10 tables exist with RLS enabled.

## 5. Verify + seed + reset (creds needed; DATABASE_MODE=supabase)

```bash
python scripts/verify_supabase_connection.py
```
- [ ] Reports connected=true, lists all 10 tables, shows seeded counts.

```bash
python scripts/seed_supabase_test_data.py
```
- [ ] Idempotent: run twice → second run adds 0 rows (on conflict do nothing).
- [ ] Prints per-table seeded counts for batch `20260721_whatsapp_agent_seed_v1`.

```bash
python scripts/reset_supabase_test_data.py
```
- [ ] Deletes only seeded rows; a manually-inserted `is_test_data=false` row
      survives; no table is truncated.

## 6. API against Supabase (creds needed; DATABASE_MODE=supabase)

```bash
curl localhost:8100/health/db                 # backend=supabase, connected=true
curl localhost:8100/api/conversations         # 6 seeded conversations
curl localhost:8100/api/orders/active         # active seeded orders
curl localhost:8100/api/flags?status=open     # open flags (refund/damaged/b2b/payment)
```
- [ ] Refund conversation has `human_intervention_required=true`,
      `priority=urgent`, `handoff_reason='Refund request'`.
- [ ] `POST /api/conversations/{id}/human-takeover` → status `human_takeover`.
- [ ] `POST /api/conversations/{id}/human-message` `{ "text": "…" }` stores a
      human message.
- [ ] `POST /api/conversations/{id}/return-to-bot` → status `bot`.
- [ ] `POST /api/conversations/{id}/resolve` → status `resolved`.
- [ ] `POST /api/flags/{flag_id}/resolve` → flag status `resolved`.
- [ ] No customer phone/full address appears in any response (masked/area only).

## 7. Dashboard (frontend)

```bash
cd apps/admin && npm run typecheck          # 0 errors
```
- [ ] `whatsapp-agent-api.ts` exposes listConversations/getConversation/
      getMessages/startHumanTakeover/returnToBot/sendHumanMessage/
      resolveConversation/listFlags/listOrders/listActiveOrders/
      listCompletedOrders/getOrder + dbHealth.
- [ ] Inbox shows **Test Data** + **Demo Conversation** badges on seeded rows.
