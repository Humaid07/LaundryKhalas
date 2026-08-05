# Runbook — Apply migration 000039 (WhatsApp intent classifications)

**Migration:** `supabase/migrations/20260805_000039_whatsapp_message_classifications.sql`
**Target:** the **dev/test** Supabase project ONLY (never production).
**Effect:** creates `whatsapp_message_classifications` (+ unique idempotency
constraint, range CHECK, indexes, `updated_at` trigger, RLS-deny policy). Additive
+ idempotent — safe to re-run.

## 0. Preconditions (verified 2026-08-06)
- Dependencies already in the schema: `pgcrypto` (`gen_random_uuid()`),
  `set_updated_at()`, and FK targets `customers` / `conversations` / `messages`.
- No version conflict: `000039` is independent of the other session's `000040`.
- The apply script refuses unless the environment is the dev/test project.

## 1. Set environment (dev/test only)
The safety guard (`scripts/_safety._base_problems`) requires ALL of:

```
APP_ENV=local                 # anything except "production"
DATABASE_MODE=supabase
DATABASE_ENV=test
SUPABASE_PROJECT_TYPE=test
DATABASE_URL=postgresql://<dev/test Supabase service-role DSN>
```

Put these in `apps/whatsapp-agent/.env` (already gitignored) or export them for the
command. `DATABASE_URL` must be the **backend/service-role** Postgres connection
string for the dev/test project (the pooler DSN is fine).

## 2. Apply
From `apps/whatsapp-agent` (use the venv Python):

```
./.venv/Scripts/python.exe scripts/apply_whatsapp_message_classifications.py
```

Expected: `Applying 20260805_000039_… to supabase (test)` then
`Done. Run scripts/verify_whatsapp_message_classifications.py to confirm.`
(Exit code 2 = a precondition failed — it prints exactly which one and applies
nothing.)

**Alternative (Supabase CLI):** `supabase db push` applies all pending
migrations in order (this would apply BOTH `000039` and the other session's
`000040`). Use the script above if you want to apply *only* 000039.

## 3. Verify
```
./.venv/Scripts/python.exe scripts/verify_whatsapp_message_classifications.py
```
Checks the table, the `wmc_provider_msg_version_uniq` + `wmc_confidence_chk`
constraints, the RLS-deny policy, and runs an insert + duplicate (ON CONFLICT)
round-trip inside a transaction that is ALWAYS rolled back. Prints `RESULT: ok`.

## 4. Confirm end-to-end (optional)
- `GET /api/settings/status` → `ai_status.classifier.live_ready` should be true
  once `ANTHROPIC_*` + classifier flags are set.
- Send one WhatsApp turn (allow-listed test number) → a `classification_completed`
  structlog line appears and a row lands in `whatsapp_message_classifications`
  (`shadow_mode=true`). It appears in the admin Operations conversation view's
  **Intent classifier** panel.

## 5. Rollback
```
drop table if exists whatsapp_message_classifications;
```
(Also in the migration file's header.) The classifier degrades safely without the
table — persistence simply no-ops and the shadow hook still logs.

## Notes
- The session's Supabase MCP is **read-only** by design, so it cannot apply this —
  run the script/CLI above from an environment with a write-capable DSN.
- Applying is decoupled from committing: the migration file is already in the tree;
  applying it only touches the dev/test database, not git.
