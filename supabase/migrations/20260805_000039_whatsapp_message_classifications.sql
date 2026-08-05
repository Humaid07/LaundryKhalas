-- =====================================================================
-- LaundryKhalas — WhatsApp intent classifier results
-- Migration: 20260805_000039_whatsapp_message_classifications
--
-- Target: the SEPARATE dev/test Supabase project ONLY (NOT production).
--
-- One row per classified LOGICAL customer turn (fragments are aggregated BEFORE
-- classification, so a turn may cover several provider messages — see
-- included_provider_message_ids). The classifier is an INTERNAL routing aid:
-- these rows never drive a customer-facing message on their own; in Stage 1
-- (shadow_mode=true) they are recorded + compared only.
--
-- Idempotency: unique (provider, provider_message_id, classification_version) so
-- a retried webhook / re-run of the same turn never double-inserts. Corrections
-- are stored in the corrected_* columns and NEVER overwrite the original model
-- output (spec: "Store classification corrections separately").
--
-- Token/cost/latency columns mirror the names services/metrics.py already reads
-- from message metadata, so classifier usage flows into the existing dashboards.
--
-- RLS deny posture mirrors order_photos / facility_evaluations; the backend
-- service role bypasses RLS and is the only reader/writer.
--
-- Additive + idempotent.
--
-- Rollback:
--   drop table if exists whatsapp_message_classifications;
-- =====================================================================

create table if not exists whatsapp_message_classifications (
    id                      uuid primary key default gen_random_uuid(),
    conversation_id         uuid references conversations(id) on delete cascade,
    customer_id             uuid references customers(id) on delete set null,
    -- the last/triggering inbound message of the aggregated turn
    message_id              uuid references messages(id) on delete set null,
    provider                text not null default 'evolution',
    provider_message_id     text,
    -- every provider message id folded into this one logical turn (aggregation)
    included_provider_message_ids text[] not null default '{}',

    classification_version  text not null,
    classifier_model        text,
    classifier_status       text not null default 'OK',

    primary_intent          text not null default 'UNKNOWN',
    secondary_intents       text[] not null default '{}',
    intent_confidence       numeric(4,3) not null default 0,
    service_domain          text not null default 'UNKNOWN',
    service_subtype         text,
    service_confidence      numeric(4,3) not null default 0,
    customer_goal           text not null default 'UNKNOWN',
    conversation_route      text not null default 'MAIN_AGENT',
    -- the backend router's validated decision (may differ from the model's
    -- recommended conversation_route) — recorded for shadow-mode comparison
    recommended_route       text,
    fixed_template_id       text,
    pricing_intent          text not null default 'NONE',
    payment_intent          text not null default 'NONE',
    repair_intent           text not null default 'NONE',
    complaint_type          text not null default 'NONE',
    sentiment               text not null default 'NEUTRAL',
    frustration_level       smallint not null default 0,
    urgency                 text not null default 'NORMAL',
    requires_human          boolean not null default false,
    human_reason            text,
    needs_clarification     boolean not null default false,
    clarification_topic     text,
    should_cancel_followups boolean not null default true,
    reason_codes            text[] not null default '{}',
    detected_entities       jsonb not null default '{}'::jsonb,

    -- true when this classification was produced in shadow mode (recorded, not
    -- allowed to control production routing).
    shadow_mode             boolean not null default true,

    -- usage / cost / latency (same key names as services/metrics.py)
    latency_ms              integer,
    input_tokens            integer not null default 0,
    output_tokens           integer not null default 0,
    cache_creation_tokens   integer not null default 0,
    cache_read_tokens       integer not null default 0,
    estimated_cost          numeric(10,6) not null default 0,

    -- Operations corrections — separate from the original model output, never
    -- overwriting it (analytics + evaluation feedback).
    corrected_primary_intent  text,
    corrected_service_domain  text,
    corrected_complaint_type  text,
    corrected_human_label     text,
    corrected_by              text,
    corrected_at              timestamptz,
    correction_reason         text,

    -- standard test-data markers (every business table carries these)
    is_test_data            boolean not null default false,
    is_demo                 boolean not null default false,
    environment             text    not null default 'dev',
    seed_batch_id           text,
    seed_source             text,
    test_scenario_id        text,
    created_by_seed         boolean not null default false,
    created_at              timestamptz not null default now(),
    updated_at              timestamptz not null default now()
);

-- Idempotency: one classification per (provider, provider_message_id, version).
-- A NULL provider_message_id (rare) does not participate in uniqueness, which is
-- the intended Postgres behaviour.
do $$ begin
    if not exists (select 1 from pg_constraint where conname = 'wmc_provider_msg_version_uniq') then
        alter table whatsapp_message_classifications
            add constraint wmc_provider_msg_version_uniq
            unique (provider, provider_message_id, classification_version);
    end if;
end $$;

-- Range guards (defensive; the app validates too).
do $$ begin
    if not exists (select 1 from pg_constraint where conname = 'wmc_confidence_chk') then
        alter table whatsapp_message_classifications add constraint wmc_confidence_chk
            check (intent_confidence >= 0 and intent_confidence <= 1
                   and service_confidence >= 0 and service_confidence <= 1
                   and frustration_level between 0 and 3);
    end if;
end $$;

create index if not exists idx_wmc_conversation
    on whatsapp_message_classifications (conversation_id, created_at desc);
create index if not exists idx_wmc_customer
    on whatsapp_message_classifications (customer_id, created_at desc);
create index if not exists idx_wmc_primary_intent
    on whatsapp_message_classifications (primary_intent, created_at desc);
create index if not exists idx_wmc_requires_human
    on whatsapp_message_classifications (requires_human) where requires_human = true;

drop trigger if exists set_wmc_updated_at on whatsapp_message_classifications;
create trigger set_wmc_updated_at before update on whatsapp_message_classifications
    for each row execute function set_updated_at();

-- ---- RLS deny -------------------------------------------------------------
do $$
declare t text;
begin
    foreach t in array array['whatsapp_message_classifications'] loop
        execute format('alter table %I enable row level security', t);
        execute format('revoke all on %I from anon, authenticated', t);
        execute format('drop policy if exists %I_no_public_access on %I', t, t);
        execute format(
            'create policy %I_no_public_access on %I as restrictive for all '
            'to anon, authenticated using (false) with check (false)', t, t);
    end loop;
end $$;
