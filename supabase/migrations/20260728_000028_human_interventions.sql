-- =====================================================================
-- LaundryKhalas — Human-intervention (abuse/threat takeover) state
-- Migration: 20260728_000028_human_interventions
--
-- Target: the SEPARATE dev/test Supabase project ONLY (NOT production).
--
-- Persistent lifecycle for a conversation handed to a human because of abuse,
-- threats, a customer request, or a manual takeover. The AI pause itself reuses
-- the EXISTING conversations.status = 'human_takeover' gate (api/evolution_webhooks
-- already stores-only for those conversations); this table adds the reason /
-- category / severity / assignment / timestamps / notice-idempotency the
-- Operations queue and audit trail need.
--
-- Idempotency: a PARTIAL UNIQUE index guarantees AT MOST ONE active (non-terminal)
-- intervention per conversation, so re-processing the same abusive turn (or a
-- duplicate webhook / Anthropic retry) returns the existing event instead of
-- creating a second one. The one customer holding message is gated by
-- customer_notice_sent on that single row.
--
-- Privacy (CLAUDE.md §7): sanitized_preview holds a masked, non-graphic preview
-- for list views; full text stays in the messages table behind the authorized
-- conversation view. No customer phone/address/PII is stored here.
-- Additive + idempotent.
-- =====================================================================

create table if not exists human_interventions (
    id                  uuid primary key default gen_random_uuid(),
    conversation_id     uuid not null references conversations(id) on delete cascade,

    takeover_status     text not null default 'WAITING_FOR_HUMAN'
                        check (takeover_status in ('NONE','WAITING_FOR_HUMAN','ASSIGNED',
                               'HUMAN_ACTIVE','RESOLVED','RELEASED_TO_AI','CLOSED')),
    takeover_reason     text not null default 'OTHER'
                        check (takeover_reason in ('ABUSIVE_LANGUAGE','THREAT',
                               'CUSTOMER_REQUESTED_HUMAN','COMPLAINT_ESCALATION','PAYMENT_DISPUTE',
                               'DAMAGE_OR_MISSING_ITEM','AI_FAILURE','MANUAL_TAKEOVER','OTHER')),

    -- Classification snapshot (from services/abuse_classification).
    abuse_category      text,
    abuse_target        text,
    threat_severity     text,
    confidence          numeric(4,3),
    reason_codes        jsonb not null default '[]'::jsonb,
    internal_priority   text not null default 'NORMAL'
                        check (internal_priority in ('NORMAL','MEDIUM','HIGH','CRITICAL')),

    -- What triggered it.
    flagged_message_id  uuid references messages(id) on delete set null,
    flagged_turn_id     text,
    sanitized_preview   text,                 -- masked, non-graphic last-message preview

    -- Assignment / lifecycle.
    assigned_agent_id   text,
    assigned_agent_name text,
    resolution_reason   text,
    automation_paused   boolean not null default true,
    customer_notice_sent boolean not null default false,

    flagged_at          timestamptz not null default now(),
    customer_notified_at timestamptz,
    accepted_at         timestamptz,
    resolved_at         timestamptz,
    released_to_ai_at   timestamptz,

    -- test-data markers
    is_test_data        boolean not null default false,
    is_demo             boolean not null default false,
    environment         text    not null default 'dev',
    seed_batch_id       text,
    seed_source         text,
    created_by_seed     boolean not null default false,
    created_at          timestamptz not null default now(),
    updated_at          timestamptz not null default now()
);

-- AT MOST ONE active (non-terminal) intervention per conversation → idempotency.
create unique index if not exists uniq_active_human_intervention_per_convo
    on human_interventions (conversation_id)
    where takeover_status not in ('RESOLVED','RELEASED_TO_AI','CLOSED');

create index if not exists idx_human_interventions_status
    on human_interventions (takeover_status, internal_priority);
create index if not exists idx_human_interventions_convo
    on human_interventions (conversation_id);
create index if not exists idx_human_interventions_assigned
    on human_interventions (assigned_agent_id);
create index if not exists idx_human_interventions_flagged_at
    on human_interventions (flagged_at desc);

alter table human_interventions enable row level security;

drop trigger if exists set_human_interventions_updated_at on human_interventions;
create trigger set_human_interventions_updated_at before update on human_interventions
    for each row execute function set_updated_at();

-- Denormalised takeover reason on the conversation for the queue list + gate
-- context (status already carries the pause; this adds WHY without a join).
alter table conversations add column if not exists takeover_reason text;
alter table conversations add column if not exists takeover_status text;
