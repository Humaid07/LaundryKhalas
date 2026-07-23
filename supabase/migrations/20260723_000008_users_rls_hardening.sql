-- =====================================================================
-- LaundryKhalas — users table RLS / privilege hardening
-- Migration: 20260723_000008_users_rls_hardening
--
-- Target: the SEPARATE dev/test Supabase project ONLY (NOT production).
--
-- The users table (migration 000006) has RLS ENABLED but no policies, which
-- already default-denies the PostgREST roles (anon/authenticated). This migration
-- makes that intent EXPLICIT and belt-and-suspenders:
--   * REVOKE all table privileges from anon + authenticated, so the password_hash
--     column can never be reached through Supabase's public REST/GraphQL API even
--     if RLS were ever disabled by mistake.
--   * Add a RESTRICTIVE deny-all policy for anon/authenticated as documentation.
--
-- The FastAPI backend connects via the pooler as the service/postgres role, which
-- bypasses RLS, so backend user-management (api/users.py) is unaffected.
-- Additive + idempotent.
-- =====================================================================

-- 1) No table-level grants to the public API roles.
revoke all on table users from anon;
revoke all on table users from authenticated;

-- 2) Explicit restrictive deny for the API roles (self-documenting; RLS default
--    is already deny, this makes it unmistakable).
drop policy if exists users_no_public_access on users;
create policy users_no_public_access
    on users
    as restrictive
    for all
    to anon, authenticated
    using (false)
    with check (false);
