-- =====================================================================
-- LaundryKhalas — order-state transition trigger + RLS hardening
-- Migration: 20260728_000029_order_state_trigger_and_rls
--
-- Target: the SEPARATE dev/test Supabase project ONLY (NOT production).
--
-- Closes two long-standing gaps (originally "Week 2" reference targets):
--   1. A DB-level ORDER-STATE TRIGGER that enforces the order status machine at
--      the database, as defence-in-depth behind the application guards
--      (services/order_store.set_status vocabulary + orders_repo terminal guard).
--   2. Explicit RLS hardening on orders / messages / customers — the same
--      belt-and-suspenders posture already applied to `users` in migration 000008
--      (REVOKE from the public API roles + a restrictive deny policy). The FastAPI
--      backend connects via the pooler as the service/postgres role, which
--      BYPASSES RLS, so all backend data access is unaffected.
--
-- Additive + idempotent. No existing rows are rewritten; the trigger only fires
-- on an UPDATE that actually changes `status`, so updated_at bumps and ordinary
-- field edits are untouched. Every transition the app performs is allowed
-- (draft→pickup_scheduled/active on confirm, →abandoned on draft expiry,
-- →cancelled on cancel, and forward/corrective operational moves). Only three
-- invariants are enforced (they mirror the app's own guards, so nothing breaks):
--   * the new status must be a known order status (vocabulary),
--   * a terminal order (completed / cancelled / abandoned) is final,
--   * a non-draft order can never be moved back to draft (no resurrection).
--
-- Rollback:
--   drop trigger if exists trg_orders_status_transition on orders;
--   drop function if exists enforce_order_status_transition();
--   drop policy if exists orders_no_public_access on orders;
--   drop policy if exists messages_no_public_access on messages;
--   drop policy if exists customers_no_public_access on customers;
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1) Order-state transition trigger
-- ---------------------------------------------------------------------
create or replace function enforce_order_status_transition()
returns trigger
language plpgsql
as $$
declare
    _terminal constant text[] := array['completed', 'cancelled', 'abandoned'];
    _valid    constant text[] := array[
        'draft', 'active', 'pickup_scheduled', 'picked_up', 'in_cleaning',
        'ready_for_delivery', 'out_for_delivery', 'completed', 'cancelled',
        'abandoned', 'support_required', 'cancellation_requested',
        'pickup_change_requested'
    ];
    _ref text := coalesce(old.order_id, old.id::text);
begin
    -- This function only runs when status actually changes (trigger WHEN clause).

    -- (a) Vocabulary: the target status must be a known order status.
    if not (new.status = any(_valid)) then
        raise exception 'Invalid order status "%" for order %', new.status, _ref
            using errcode = 'check_violation';
    end if;

    -- (b) Terminal immutability: a finished order cannot change status.
    if old.status = any(_terminal) then
        raise exception
            'Order % is % (terminal) and cannot transition to %',
            _ref, old.status, new.status
            using errcode = 'check_violation';
    end if;

    -- (c) No resurrection: a non-draft order can never return to draft.
    if new.status = 'draft' then
        raise exception
            'Order % cannot be moved back to draft (from %)', _ref, old.status
            using errcode = 'check_violation';
    end if;

    return new;
end;
$$;

drop trigger if exists trg_orders_status_transition on orders;
create trigger trg_orders_status_transition
    before update on orders
    for each row
    when (old.status is distinct from new.status)
    execute function enforce_order_status_transition();

-- ---------------------------------------------------------------------
-- 2) RLS hardening for orders / messages / customers
--    (RLS was already ENABLED on these in migration 000001 with no policies;
--     this makes the deny-the-public-API posture explicit, matching users/000008.)
-- ---------------------------------------------------------------------
revoke all on table orders    from anon, authenticated;
revoke all on table messages  from anon, authenticated;
revoke all on table customers from anon, authenticated;

drop policy if exists orders_no_public_access on orders;
create policy orders_no_public_access
    on orders as restrictive for all
    to anon, authenticated using (false) with check (false);

drop policy if exists messages_no_public_access on messages;
create policy messages_no_public_access
    on messages as restrictive for all
    to anon, authenticated using (false) with check (false);

drop policy if exists customers_no_public_access on customers;
create policy customers_no_public_access
    on customers as restrictive for all
    to anon, authenticated using (false) with check (false);
