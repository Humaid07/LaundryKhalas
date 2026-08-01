-- =====================================================================
-- LaundryKhalas — Facility & driver performance ratings (evaluations)
-- Migration: 20260801_000038_facility_driver_ratings
--
-- Target: the SEPARATE dev/test Supabase project ONLY (NOT production).
--
-- Internal operators evaluate facilities and drivers on 1-5 factor scores. Each
-- evaluation is an immutable historical record (new evaluations never overwrite
-- old ones — spec §6); the "current" rating is aggregated from PUBLISHED
-- evaluations in application code (services/rating_service.py).
--
-- Four tables (evaluation header + its per-factor rows, for facilities and for
-- drivers). The OFFICIAL overall_score is computed + validated on the backend
-- (weighted mean of factors, config/rating_factors.json) — the frontend live
-- preview is advisory only.
--
-- Visibility: ``partner_visible_summary`` is shown to the owning facility;
-- ``internal_notes`` are internal-only and never returned by partner endpoints.
-- ``status`` gates partner visibility (only 'published' is partner-visible).
--
-- Constraints: factor scores + overall in [1,5]; weights >= 0. RLS deny posture
-- mirrors facility_audit_log / order_photos; the backend service role bypasses
-- RLS and is the only reader/writer, scoped by facility/driver in app SQL.
--
-- Additive + idempotent.
--
-- Rollback:
--   drop table if exists driver_evaluation_factors;
--   drop table if exists driver_evaluations;
--   drop table if exists facility_evaluation_factors;
--   drop table if exists facility_evaluations;
-- =====================================================================

-- ---- facility evaluations -------------------------------------------------
create table if not exists facility_evaluations (
    id                     uuid primary key default gen_random_uuid(),
    facility_id            uuid not null references facilities(id) on delete cascade,
    evaluation_date        date not null default current_date,
    evaluation_period_start date,
    evaluation_period_end  date,
    overall_score          numeric(3,2) not null,
    partner_visible_summary text,
    internal_notes         text,
    status                 text not null default 'published'
                           check (status in ('draft', 'published', 'archived')),
    created_by_user_id     uuid,
    updated_by_user_id     uuid,
    is_test_data           boolean not null default false,
    is_demo                boolean not null default false,
    environment            text    not null default 'dev',
    seed_batch_id          text,
    seed_source            text,
    test_scenario_id       text,
    created_by_seed        boolean not null default false,
    created_at             timestamptz not null default now(),
    updated_at             timestamptz not null default now()
);

do $$ begin
    if not exists (select 1 from pg_constraint where conname = 'facility_evaluations_overall_chk') then
        alter table facility_evaluations add constraint facility_evaluations_overall_chk
            check (overall_score >= 1 and overall_score <= 5);
    end if;
end $$;

create index if not exists idx_facility_evaluations_facility
    on facility_evaluations (facility_id, status, evaluation_date desc);

drop trigger if exists set_facility_evaluations_updated_at on facility_evaluations;
create trigger set_facility_evaluations_updated_at before update on facility_evaluations
    for each row execute function set_updated_at();

create table if not exists facility_evaluation_factors (
    id             uuid primary key default gen_random_uuid(),
    evaluation_id  uuid not null references facility_evaluations(id) on delete cascade,
    factor_key     text not null,
    factor_label   text not null,
    score          numeric(3,2) not null,
    weight         numeric(6,3) not null default 1.0,
    weighted_score numeric(6,3) not null default 0,
    created_at     timestamptz not null default now(),
    unique (evaluation_id, factor_key)
);

do $$ begin
    if not exists (select 1 from pg_constraint where conname = 'facility_eval_factor_score_chk') then
        alter table facility_evaluation_factors add constraint facility_eval_factor_score_chk
            check (score >= 1 and score <= 5 and weight >= 0);
    end if;
end $$;

create index if not exists idx_facility_eval_factors_eval
    on facility_evaluation_factors (evaluation_id);

-- ---- driver evaluations ---------------------------------------------------
create table if not exists driver_evaluations (
    id                     uuid primary key default gen_random_uuid(),
    driver_id              uuid not null references facility_drivers(id) on delete cascade,
    facility_id            uuid references facilities(id) on delete set null,
    evaluation_date        date not null default current_date,
    evaluation_period_start date,
    evaluation_period_end  date,
    overall_score          numeric(3,2) not null,
    partner_visible_summary text,
    internal_notes         text,
    status                 text not null default 'published'
                           check (status in ('draft', 'published', 'archived')),
    created_by_user_id     uuid,
    updated_by_user_id     uuid,
    is_test_data           boolean not null default false,
    is_demo                boolean not null default false,
    environment            text    not null default 'dev',
    seed_batch_id          text,
    seed_source            text,
    test_scenario_id       text,
    created_by_seed        boolean not null default false,
    created_at             timestamptz not null default now(),
    updated_at             timestamptz not null default now()
);

do $$ begin
    if not exists (select 1 from pg_constraint where conname = 'driver_evaluations_overall_chk') then
        alter table driver_evaluations add constraint driver_evaluations_overall_chk
            check (overall_score >= 1 and overall_score <= 5);
    end if;
end $$;

create index if not exists idx_driver_evaluations_driver
    on driver_evaluations (driver_id, status, evaluation_date desc);
create index if not exists idx_driver_evaluations_facility
    on driver_evaluations (facility_id, status);

drop trigger if exists set_driver_evaluations_updated_at on driver_evaluations;
create trigger set_driver_evaluations_updated_at before update on driver_evaluations
    for each row execute function set_updated_at();

create table if not exists driver_evaluation_factors (
    id             uuid primary key default gen_random_uuid(),
    evaluation_id  uuid not null references driver_evaluations(id) on delete cascade,
    factor_key     text not null,
    factor_label   text not null,
    score          numeric(3,2) not null,
    weight         numeric(6,3) not null default 1.0,
    weighted_score numeric(6,3) not null default 0,
    created_at     timestamptz not null default now(),
    unique (evaluation_id, factor_key)
);

do $$ begin
    if not exists (select 1 from pg_constraint where conname = 'driver_eval_factor_score_chk') then
        alter table driver_evaluation_factors add constraint driver_eval_factor_score_chk
            check (score >= 1 and score <= 5 and weight >= 0);
    end if;
end $$;

create index if not exists idx_driver_eval_factors_eval
    on driver_evaluation_factors (evaluation_id);

-- ---- RLS deny (all four tables) -------------------------------------------
do $$
declare t text;
begin
    foreach t in array array[
        'facility_evaluations', 'facility_evaluation_factors',
        'driver_evaluations', 'driver_evaluation_factors'
    ] loop
        execute format('alter table %I enable row level security', t);
        execute format('revoke all on %I from anon, authenticated', t);
        execute format('drop policy if exists %I_no_public_access on %I', t, t);
        execute format(
            'create policy %I_no_public_access on %I as restrictive for all '
            'to anon, authenticated using (false) with check (false)', t, t);
    end loop;
end $$;
