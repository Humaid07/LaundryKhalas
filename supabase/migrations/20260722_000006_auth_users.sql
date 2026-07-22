-- =====================================================================
-- LaundryKhalas — dashboard auth users + RBAC
-- Migration: 20260722_000006_auth_users
--
-- Target: the SEPARATE dev/test Supabase project ONLY (NOT production).
--
-- Backend-owned auth (Dashboard → FastAPI → Supabase). Users authenticate
-- against FastAPI, which issues signed JWTs and enforces role on every /api/*
-- call. Passwords are PBKDF2-HMAC-SHA256 (services/auth.py) — never plaintext.
-- Roles: 'admin' (full access) | 'operations' (Orders + linked Operations chat).
-- Additive + idempotent.
-- =====================================================================

create table if not exists users (
    id            uuid primary key default gen_random_uuid(),
    email         text unique not null,          -- stored lower-cased
    password_hash text not null,
    full_name     text,
    role          text not null default 'operations'
                  check (role in ('admin', 'operations')),
    is_active     boolean not null default true,
    market        text,                           -- optional scope (null = all)
    environment   text not null default 'dev',
    created_by_seed boolean not null default false,
    created_at    timestamptz not null default now(),
    updated_at    timestamptz not null default now()
);
create index if not exists users_email_idx on users (lower(email));

alter table users enable row level security;

drop trigger if exists set_users_updated_at on users;
create trigger set_users_updated_at before update on users
    for each row execute function set_updated_at();
