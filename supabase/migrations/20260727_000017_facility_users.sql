-- =====================================================================
-- LaundryKhalas — Facility user roles + per-user facility scope
-- Migration: 20260727_000017_facility_users
--
-- Target: the SEPARATE dev/test Supabase project ONLY (NOT production).
--
-- Extends the existing `public.users` RBAC (admin | operations) with facility
-- roles and a `facility_id` scope column (mirrors the existing `market` scope).
-- A facility user is confined to their own facility_id — enforced in the backend
-- (api/deps.require_facility_scope), since the service role bypasses RLS.
-- The actual facility owner login is seeded by scripts/seed_facility_data.py
-- (password hashing needs Python — see services/auth.hash_password).
-- Additive + idempotent.
-- =====================================================================

-- Widen the role CHECK to include the facility roles (drop the inline-named
-- constraint from 000006, re-add as a named one covering all roles).
alter table public.users drop constraint if exists users_role_check;
alter table public.users add constraint users_role_check
    check (role in ('admin', 'operations',
                    'facility_owner', 'facility_manager', 'facility_staff', 'facility_driver'));

-- Per-user facility scope (null = not facility-scoped, e.g. platform staff).
alter table public.users add column if not exists facility_id uuid references facilities(id) on delete set null;
create index if not exists users_facility_idx on public.users (facility_id);
