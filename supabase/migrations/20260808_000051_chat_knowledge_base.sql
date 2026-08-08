-- 000051 — chat_knowledge_base: redacted past-conversation retrieval KB (Phase 2 of
-- the knowledge-reinforcement work).
--
-- Real customer WhatsApp chats (chats_html.zip) are parsed, PII-REDACTED
-- (services/privacy + services/sanitize: phones/emails/names/addresses removed),
-- chunked into exchanges, and embedded locally with fastembed (BAAI/bge-small-en-v1.5,
-- 384-dim). The agent's `search_past_conversations` tool embeds a query and does a
-- cosine-similarity lookup here to ground its replies in real precedent. NO raw PII is
-- ever stored — only redacted text + its vector. Runtime source of truth is this table;
-- scripts/index_chat_kb.py (re-runnable) populates it. Mirrors nothing in the SQLite ORM
-- (retrieval is Supabase/pgvector-only; the hermetic test suite mocks the embedder).
--
-- Idempotent: safe to re-run.

create extension if not exists vector;

create table if not exists chat_knowledge_base (
    id uuid primary key default gen_random_uuid(),
    source_ref text not null,            -- redacted conversation label (e.g. masked/hashed number)
    chunk_index integer not null default 0,
    market text not null default 'AE',
    content text not null,               -- REDACTED conversation chunk (no PII)
    embedding vector(384) not null,      -- BAAI/bge-small-en-v1.5
    token_estimate integer,
    dedupe_key text not null unique,     -- sha1(source_ref|chunk_index) — index at most once
    created_at timestamptz not null default now()
);

-- Approximate-nearest-neighbour index for cosine similarity (bge is cosine-normalised).
create index if not exists idx_chat_kb_embedding
    on chat_knowledge_base using hnsw (embedding vector_cosine_ops);
create index if not exists idx_chat_kb_market on chat_knowledge_base (market);

-- RLS deny-all; only the backend service role (which bypasses RLS) reads/writes. Even
-- redacted precedent must never be exposed to anon/end-user roles.
alter table chat_knowledge_base enable row level security;
do $$
begin
    if not exists (
        select 1 from pg_policies
        where tablename = 'chat_knowledge_base' and policyname = 'chat_knowledge_base_deny_all'
    ) then
        create policy chat_knowledge_base_deny_all on chat_knowledge_base
            for all using (false) with check (false);
    end if;
end $$;

comment on table chat_knowledge_base is
    'Redacted past-conversation retrieval KB (Phase 2). Populated by scripts/index_chat_kb.py from real chats after PII redaction; queried by the search_past_conversations agent tool via pgvector cosine similarity. NO raw PII stored.';
