-- 000040 — Stripe-first payment state on orders (spec §13).
--
-- Backend-authoritative payment preference + the deterministic escalation
-- timestamps produced by services/payment_preference.py. The WhatsApp model never
-- writes these directly; a backend tool resolves the state and persists it here so
-- payment behaviour is auditable and a Stripe link / cash-on-delivery decision is
-- never invented. Mirrors the SQLite ORM columns in models.py (Order).
--
-- Idempotent: safe to re-run.

alter table orders
    add column if not exists payment_preference text not null default 'UNDECIDED',
    add column if not exists stripe_preference_explained_at timestamptz,
    add column if not exists stripe_no_account_explained_at timestamptz,
    add column if not exists cash_requested_at timestamptz,
    add column if not exists cash_accepted_at timestamptz,
    add column if not exists payment_followup_stage integer not null default 0;

-- Guard the vocabulary (UNDECIDED | STRIPE | CASH_ON_DELIVERY) without failing on
-- pre-existing rows (all default to UNDECIDED above).
do $$
begin
    if not exists (
        select 1 from pg_constraint where conname = 'orders_payment_preference_check'
    ) then
        alter table orders
            add constraint orders_payment_preference_check
            check (payment_preference in ('UNDECIDED', 'STRIPE', 'CASH_ON_DELIVERY'));
    end if;
end $$;

comment on column orders.payment_preference is
    'Stripe-first payment state (spec §13): UNDECIDED | STRIPE | CASH_ON_DELIVERY. Backend-authoritative.';
