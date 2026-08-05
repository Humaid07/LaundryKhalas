-- 000042 — scheduled_followups: the durable queue for the centralized follow-up
-- scheduler (spec §§14, 24, 25).
--
-- The scheduling POLICY (timing, the 10 PM cutoff, suppression, and the
-- "only the most relevant follow-up" arbitration) lives in services/followups.py and
-- is pure. This table is only the queue a sweeper reads: it loads PENDING rows that are
-- due, asks the policy which single one to send per conversation, sends it, and marks it
-- SENT (or CANCELLED / SUPPRESSED). `dedupe_key` is unique so a given follow-up is
-- scheduled at most once. Mirrors the SQLite ORM model in models.py (ScheduledFollowup).
--
-- Idempotent: safe to re-run.

create table if not exists scheduled_followups (
    id uuid primary key default gen_random_uuid(),
    conversation_id uuid,
    order_id text,
    customer_phone text,
    followup_type text not null,
    status text not null default 'PENDING'
        check (status in ('PENDING', 'SENT', 'CANCELLED', 'SUPPRESSED')),
    template_id text,
    dedupe_key text not null unique,
    due_at timestamptz not null,
    anchor_at timestamptz,
    market text not null default 'AE',
    persona text,
    payload jsonb,
    suppressed_reason text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    sent_at timestamptz,
    cancelled_at timestamptz
);

-- The sweeper polls PENDING rows ordered by due time.
create index if not exists idx_scheduled_followups_due
    on scheduled_followups (status, due_at);
create index if not exists idx_scheduled_followups_conversation
    on scheduled_followups (conversation_id);

-- Row-level security: deny by default; the service role (backend) bypasses RLS, so the
-- sweeper still reads/writes. No end-user/anon access to the outreach queue.
alter table scheduled_followups enable row level security;
do $$
begin
    if not exists (
        select 1 from pg_policies
        where tablename = 'scheduled_followups' and policyname = 'scheduled_followups_deny_all'
    ) then
        create policy scheduled_followups_deny_all on scheduled_followups
            for all using (false) with check (false);
    end if;
end $$;

comment on table scheduled_followups is
    'Durable queue for the centralized follow-up scheduler (spec §§14/24/25). Policy is in services/followups.py; this is only the queue.';
