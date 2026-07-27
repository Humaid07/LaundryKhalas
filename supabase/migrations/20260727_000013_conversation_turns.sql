-- =====================================================================
-- LaundryKhalas — DURABLE CONVERSATION TURNS (message aggregation)
-- Migration: 20260727_000013_conversation_turns
--
-- Target: the SEPARATE dev/test Supabase project ONLY (NOT production).
--
-- A "conversation turn" groups the rapid inbound fragments a customer sends as
-- one thought so the agent processes them together and replies ONCE (task spec
-- §§14-23). Each raw message row still exists for per-message wa_message_id
-- dedup + audit; a turn links its fragments via messages.turn_id and carries the
-- aggregation window + processing status so an in-flight turn SURVIVES A RESTART
-- (spec §§21/27).
--
-- Status lifecycle: pending -> aggregating -> processing -> completed | failed
-- (cancelled for takeover/abandon). Additive + idempotent.
-- =====================================================================

create table if not exists conversation_turns (
    id                       uuid primary key default gen_random_uuid(),
    turn_id                  text unique not null,          -- stable public id, turn_<hex>
    conversation_id          uuid not null references conversations(id) on delete cascade,
    customer_id              uuid,
    direction                text not null default 'inbound',
    status                   text not null default 'pending',
        -- pending | aggregating | processing | completed | failed | cancelled
    first_message_at         timestamptz not null default now(),
    last_message_at          timestamptz not null default now(),
    aggregation_deadline_at  timestamptz,                   -- process by this time
    processed_at             timestamptz,
    combined_text            text,                          -- the combined logical input
    message_count            int  not null default 0,
    attempts                 int  not null default 0,       -- processing attempts (bounded retry)
    llm_request_id           text,
    response_message_id      text,
    created_at               timestamptz not null default now(),
    updated_at               timestamptz not null default now()
);

-- One open turn per conversation is the norm; index the open + due lookups.
create index if not exists conversation_turns_open_idx
    on conversation_turns (conversation_id)
    where status in ('pending', 'aggregating');
create index if not exists conversation_turns_due_idx
    on conversation_turns (aggregation_deadline_at)
    where status in ('pending', 'aggregating');
create index if not exists conversation_turns_status_idx
    on conversation_turns (status);

alter table conversation_turns enable row level security;

drop trigger if exists set_conversation_turns_updated_at on conversation_turns;
create trigger set_conversation_turns_updated_at before update on conversation_turns
    for each row execute function set_updated_at();

-- Link each raw message to the turn it belongs to (audit: which fragments
-- produced which agent response — spec §18). Nullable: pre-aggregation and
-- non-aggregated messages simply have no turn_id.
alter table messages add column if not exists turn_id text;
create index if not exists messages_turn_id_idx on messages (turn_id) where turn_id is not null;
