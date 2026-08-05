-- 000043 — web_order_intents: website "Order Now" click capture (spec §24).
--
-- Every click is recorded for analytics. Abandonment follow-ups (WEB_ABANDONMENT_1/2/3)
-- are scheduled ONLY when the visitor is identified + consented + has a verified WhatsApp
-- number (services/web_order_intent decides; services/followup_scheduler queues). No
-- fingerprinting — the number is stored only when the visitor supplied it. A prefilled but
-- unsent WhatsApp message is never treated as an inbound conversation. Mirrors the SQLite
-- ORM model in models.py (WebOrderIntent).
--
-- Idempotent: safe to re-run.

create table if not exists web_order_intents (
    id uuid primary key default gen_random_uuid(),
    session_id text not null,
    source_page text,
    service_code text,
    market text not null default 'AE',
    campaign jsonb,
    customer_id uuid,
    whatsapp_number text,
    consent boolean not null default false,
    outreach_scheduled boolean not null default false,
    outreach_reason text,
    converted boolean not null default false,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_web_order_intents_session on web_order_intents (session_id);
create index if not exists idx_web_order_intents_created on web_order_intents (created_at);

-- RLS deny-all; only the backend service role (which bypasses RLS) reads/writes. The
-- captured number + consent must never be exposed to anon/end-user roles.
alter table web_order_intents enable row level security;
do $$
begin
    if not exists (
        select 1 from pg_policies
        where tablename = 'web_order_intents' and policyname = 'web_order_intents_deny_all'
    ) then
        create policy web_order_intents_deny_all on web_order_intents
            for all using (false) with check (false);
    end if;
end $$;

comment on table web_order_intents is
    'Website Order-Now click capture (spec §24). Outreach only for identified+consented visitors; never fingerprinted.';
