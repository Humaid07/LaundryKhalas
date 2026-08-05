-- 000045 — order rule-set version (spec §§17, 29).
--
-- The WhatsApp service rule-set version the order's pricing was produced under, stamped at
-- confirmation so a price always traces to the exact rules that made it. Surfaced on the
-- order-detail dashboard. Mirrors the SQLite ORM column in models.py (Order.rule_version).
-- Additive + idempotent.

alter table orders add column if not exists rule_version text;

comment on column orders.rule_version is
    'WhatsApp service rule-set version the order was priced under (spec §§17, 29). Stamped at confirmation.';
