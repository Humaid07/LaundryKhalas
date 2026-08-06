# Runbook — Apply migration 000046 (facility order experience)

**Migration:** `supabase/migrations/20260806_000046_facility_order_experience.sql`
**Target:** the SEPARATE dev/test Supabase project ONLY (`inutjbnmyvfjijvbudun`). NOT production.
**Date prepared:** 2026-08-06

## What it changes (all additive + idempotent)

- `order_notes.priority` — `NORMAL | IMPORTANT | CRITICAL` (default `NORMAL`, CHECK-constrained).
- `order_photos` — `order_item_id` (soft per-item link), `caption`, `source`
  (`CUSTOMER | DRIVER | OPERATIONS | FACILITY_BEFORE_PROCESSING | FACILITY_AFTER_PROCESSING |
  FACILITY_ISSUE | INSPECTION`, CHECK-constrained) + partial index on `order_item_id`.
- `orders` — `facility_fee_snapshot (jsonb)`, `facility_fee_total (numeric)`, `facility_fee_currency (text)`
  (immutable per-order facility-fee snapshot; never recomputed from a newer rate card).
- `facility_order_reviews` — NEW table (versioned "details reviewed" acknowledgement) + indexes + RLS deny.

## Why it must be applied before the new SELECTs run against real Supabase

`db/repositories/order_notes_repo._COLS` and `order_photos_repo._SELECT_COLS` now select the new
columns; `facility_order_reviews_repo` reads/writes the new table. Against the dev/test Supabase these
queries fail until the columns/table exist. The hermetic pytest suite is unaffected (SQLite; these
asyncpg paths are monkeypatched), so **tests pass without applying the migration**, but the live
Facility Dashboard detail view / acknowledge endpoint require it.

## Apply (psql / Supabase SQL editor)

The MCP Supabase plugin is scoped read-only, so DDL must go through psql or the SQL editor:

```bash
psql "$SUPABASE_DB_URL" -f supabase/migrations/20260806_000046_facility_order_experience.sql
```

## Verify

```sql
select column_name from information_schema.columns
 where table_name = 'order_notes' and column_name = 'priority';                         -- 1 row
select column_name from information_schema.columns
 where table_name = 'order_photos' and column_name in ('order_item_id','caption','source'); -- 3 rows
select column_name from information_schema.columns
 where table_name = 'orders' and column_name like 'facility_fee%';                      -- 3 rows
select to_regclass('public.facility_order_reviews');                                    -- not null
```

## Rollback

See the `Rollback:` block at the top of the migration file (drops the new table/columns/constraints).
