-- 000041 — Stripe Invoicing linkage on orders (spec §13, Phase 2b live payments).
--
-- Backend-authoritative payment/settlement state for a STRIPE order. Written by
-- services/payments (invoice create) and by the /webhooks/stripe handler (payment
-- reported by Stripe). The WhatsApp model never writes these. Mirrors the SQLite
-- ORM columns in models.py (Order). Amounts are in MINOR units (fils/cents).
--
-- Idempotent: safe to re-run.

alter table orders
    add column if not exists stripe_customer_id text,
    add column if not exists stripe_invoice_id text,
    add column if not exists stripe_hosted_invoice_url text,
    add column if not exists stripe_invoice_pdf_url text,
    add column if not exists payment_status text not null default 'unpaid',
    add column if not exists amount_paid_minor integer,
    add column if not exists payment_currency text,
    add column if not exists paid_at timestamptz;

-- Fast lookup from a webhook (event carries the Stripe invoice id → our order).
create index if not exists idx_orders_stripe_invoice_id
    on orders (stripe_invoice_id)
    where stripe_invoice_id is not null;

-- Guard the settlement vocabulary without failing on pre-existing rows
-- (all default to 'unpaid' above).
do $$
begin
    if not exists (
        select 1 from pg_constraint where conname = 'orders_payment_status_check'
    ) then
        alter table orders
            add constraint orders_payment_status_check
            check (payment_status in ('unpaid', 'pending', 'paid', 'failed', 'refunded', 'void'));
    end if;
end $$;

comment on column orders.payment_status is
    'Settlement state for a Stripe order (spec §13): unpaid|pending|paid|failed|refunded|void. Backend/webhook-authoritative.';
comment on column orders.stripe_invoice_id is
    'Stripe Invoice id (in_...) for this order; the /webhooks/stripe handler maps an inbound invoice.paid event back to the order via this column.';
