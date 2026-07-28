# Build Report — Order-State Trigger + RLS Hardening (migration 000029)

**Date:** 2026-07-28
**Migration:** `supabase/migrations/20260728_000029_order_state_trigger_and_rls.sql`

## Objective
Close two long-standing gaps (originally prototype "Week 2" reference targets):
a **DB-level order-state trigger** and explicit **RLS policies on
orders / messages / customers**. Defence-in-depth behind the existing application
guards — not a behavior change.

## Background (why they were missing)
Audit (see the RLS/trigger Q&A): RLS was *enabled* on orders/messages/customers
since migration 000001 but with **no policies** (deny-public posture; backend uses
the service role which bypasses RLS). The only prior policy was `users_no_public_access`
(000008). Order-state validity lived only in app code (`services/order_store`,
`services/booking_flow`, and the guarded compare-and-set in
`orders_repo.confirm_booking`) — there was **no DB trigger** and no status CHECK.

## What was added (migration 000029)
1. **Order-state trigger** — `enforce_order_status_transition()` +
   `trg_orders_status_transition` (`BEFORE UPDATE ON orders`, `WHEN (old.status IS
   DISTINCT FROM new.status)` so it only fires on real status changes). Enforces
   three invariants that mirror the app's own guards (so nothing breaks):
   - **vocabulary** — target status must be one of the 13 known statuses;
   - **terminal immutability** — completed / cancelled / abandoned are final;
   - **no resurrection** — a non-draft order can never return to draft.
   Every transition the app performs is allowed (confirm draft→pickup_scheduled/active,
   draft→abandoned on expiry, X→cancelled, and forward/corrective operational moves).
2. **RLS hardening** — mirrors the `users`/000008 pattern for orders, messages,
   customers: `REVOKE ALL … FROM anon, authenticated` + a `restrictive` deny-all
   policy (`using(false) with check(false)`). The service-role backend bypasses RLS,
   so data access is unaffected; this formalizes "the public API can never read
   these tables directly."

Additive + idempotent; rollback SQL is in the migration header. No existing rows
are rewritten (trigger is UPDATE-only, fires only on status change).

## Verification (applied to the dev/test Supabase)
Applied via asyncpg (repo convention — no generic runner) and smoke-tested with
temp rows inside a transaction that was **rolled back** (no data persisted):

| Check | Result |
|---|---|
| trigger + function present | ✅ |
| RLS deny policies on orders/messages/customers | ✅ (all 3) |
| `draft → pickup_scheduled` (the live confirm path) | ✅ allowed |
| forward → `completed` | ✅ allowed |
| `pickup_scheduled → cancelled` | ✅ allowed |
| `completed → active` (terminal) | ✅ blocked (23514) |
| `pickup_scheduled → draft` (resurrect) | ✅ blocked (23514) |
| `→ banana` (bad vocabulary) | ✅ blocked (23514) |

`draft → pickup_scheduled` passing confirms the live booking-confirm flow is
unaffected. Re-check anytime with:
```
cd apps/whatsapp-agent
python scripts/verify_order_state_and_rls.py     # → RESULT: ALL GOOD
```

## How to check (also directly in SQL)
```sql
select tgname from pg_trigger where tgname='trg_orders_status_transition';
select tablename, policyname from pg_policies
 where tablename in ('orders','messages','customers');
```

## Files
- **New:** the migration, `scripts/verify_order_state_and_rls.py`, this report.
- **Updated:** `docs/architecture/supabase-dev-database.md` (RLS note), `docs/00-Home.md`.

## Known limitations / next steps
- No column `CHECK` on `orders.status` (would fail if any legacy row held an
  out-of-vocab status); the trigger validates vocabulary on transition instead.
- RLS remains **deny-public + service-role**, not per-user/market row policies —
  granular tenant RLS is still deferred to the production project (unchanged).
- Applied to the **dev/test** Supabase only; production gets its own auth/RLS design.
- `messages`/`customers` gain no trigger (no state machine); only the RLS policy.
