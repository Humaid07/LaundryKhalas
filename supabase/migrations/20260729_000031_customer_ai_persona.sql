-- Migration 000031 — persistent per-customer AI persona assignment
--
-- Adds the fields that pin ONE approved WhatsApp AI-agent persona name
-- (Sara/Maya/Zoya/Hanna/Sofia/Max/Ben) to a customer for life. The name is chosen
-- once (deterministic/balanced backend strategy) on first contact and never changes
-- across new orders, conversations, restarts or deployments. Only the DISPLAYED name
-- differs between personas — all operational behaviour is identical. AI personas are
-- kept separate from human Operations staff (who use their real names during takeover).
--
-- Idempotent (add-column-if-not-exists). Rollback at the bottom.

alter table customers add column if not exists assigned_ai_persona_id       text;
alter table customers add column if not exists assigned_ai_persona_name     text;
alter table customers add column if not exists ai_persona_assigned_at        timestamptz;
alter table customers add column if not exists ai_persona_assignment_version integer;

-- Fast "already assigned?" lookups and per-persona balance reporting.
create index if not exists idx_customers_ai_persona on customers (assigned_ai_persona_id);

-- ROLLBACK (manual):
-- drop index if exists idx_customers_ai_persona;
-- alter table customers drop column if exists ai_persona_assignment_version;
-- alter table customers drop column if exists ai_persona_assigned_at;
-- alter table customers drop column if exists assigned_ai_persona_name;
-- alter table customers drop column if exists assigned_ai_persona_id;
