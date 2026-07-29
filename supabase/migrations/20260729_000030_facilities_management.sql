-- =====================================================================
-- LaundryKhalas — Facilities Management (admin + partner CRUD surface)
-- Migration: 20260729_000030_facilities_management
--
-- Target: the SEPARATE dev/test Supabase project ONLY (NOT production).
--
-- Adds the fields the Facilities Management module needs on top of the existing
-- facility subsystem (000016 facilities, 000020 facility_settings/timings,
-- 000027 facility_services/rates). Nothing here rewrites existing rows.
--
--   1. facilities: full_address, quality_score (INTERNAL-ONLY, 0..100, nullable),
--      capacity_unit (the unit for the existing capacity_daily value),
--      onboarding_source (admin_dashboard|partner_portal), created_by/updated_by.
--   2. facility_timings: is_24h flag (structured weekly hours already exist; this
--      lets a day be marked open 24 hours without abusing opens_at/closes_at).
--   3. facility_audit_log: a facility-scoped audit trail (before/after JSON) for
--      create / update / status / rates / quality / services / hours changes —
--      mirrors the immutable pricing_audit_log pattern (000009). Facility-level
--      actions are not order-scoped, so order_events can't carry them.
--
-- quality_score and internal rates (facility_rates, 000027) are INTERNAL-ONLY and
-- are never returned by partner-facing serializers. This migration only adds the
-- column; the partner API/serializer exclusion is enforced in application code.
--
-- RLS: facility_audit_log gets the same belt-and-suspenders deny posture applied
-- to users (000008) and orders/messages/customers (000029). The FastAPI backend
-- connects as the service/postgres role via the pooler, which BYPASSES RLS, so
-- backend access is unaffected.
--
-- Additive + idempotent.
--
-- Rollback:
--   drop policy if exists facility_audit_log_no_public_access on facility_audit_log;
--   drop table if exists facility_audit_log;
--   alter table facility_timings drop column if exists is_24h;
--   alter table facilities
--     drop column if exists full_address,
--     drop column if exists quality_score,
--     drop column if exists capacity_unit,
--     drop column if exists onboarding_source,
--     drop column if exists created_by,
--     drop column if exists updated_by;
--   drop index if exists facilities_status_idx;
--   drop index if exists facilities_emirate_idx;
-- =====================================================================

-- ---------------------------------------------------------------------
-- 1) facilities — management fields
-- ---------------------------------------------------------------------
alter table facilities add column if not exists full_address     text;
alter table facilities add column if not exists quality_score    numeric(5,2);
alter table facilities add column if not exists capacity_unit    text not null default 'orders_per_day';
alter table facilities add column if not exists onboarding_source text not null default 'admin_dashboard';
alter table facilities add column if not exists created_by       uuid references public.users(id) on delete set null;
alter table facilities add column if not exists updated_by       uuid references public.users(id) on delete set null;

-- CHECK constraints (guard against re-adding if already present).
do $$
begin
    if not exists (select 1 from pg_constraint where conname = 'facilities_quality_score_check') then
        alter table facilities add constraint facilities_quality_score_check
            check (quality_score is null or (quality_score >= 0 and quality_score <= 100));
    end if;
    if not exists (select 1 from pg_constraint where conname = 'facilities_capacity_unit_check') then
        alter table facilities add constraint facilities_capacity_unit_check
            check (capacity_unit in ('orders_per_day', 'kg_per_day', 'pieces_per_day'));
    end if;
    if not exists (select 1 from pg_constraint where conname = 'facilities_onboarding_source_check') then
        alter table facilities add constraint facilities_onboarding_source_check
            check (onboarding_source in ('admin_dashboard', 'partner_portal'));
    end if;
end $$;

-- Filter/lookup indexes for the management list (status + emirate filters).
create index if not exists facilities_status_idx  on facilities (operating_status);
create index if not exists facilities_emirate_idx on facilities (emirate);

-- ---------------------------------------------------------------------
-- 2) facility_timings — 24-hour flag
-- ---------------------------------------------------------------------
alter table facility_timings add column if not exists is_24h boolean not null default false;

-- ---------------------------------------------------------------------
-- 3) facility_audit_log — facility-scoped change trail
-- ---------------------------------------------------------------------
create table if not exists facility_audit_log (
    id           uuid primary key default gen_random_uuid(),
    facility_id  uuid references facilities(id) on delete cascade,
    action       text not null,        -- facility_created|facility_updated|status_changed|
                                        -- rates_changed|quality_changed|services_changed|hours_changed|capacity_changed
    actor_id     uuid,                  -- users.id (nullable; agent/system actions have no user row)
    actor_type   text not null default 'internal',  -- internal|partner|agent|system
    source_app   text,                  -- admin_dashboard|partner_portal|whatsapp_agent
    before_json  jsonb,
    after_json   jsonb,
    created_at   timestamptz not null default now()
);
create index if not exists facility_audit_log_facility_idx on facility_audit_log (facility_id, created_at desc);
create index if not exists facility_audit_log_action_idx   on facility_audit_log (action);

alter table facility_audit_log enable row level security;
-- Belt-and-suspenders: deny the PostgREST API roles; backend service role bypasses RLS.
revoke all on facility_audit_log from anon, authenticated;
drop policy if exists facility_audit_log_no_public_access on facility_audit_log;
create policy facility_audit_log_no_public_access on facility_audit_log
    as restrictive for all to anon, authenticated
    using (false) with check (false);
