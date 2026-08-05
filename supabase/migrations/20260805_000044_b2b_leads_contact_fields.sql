-- 000044 — B2B lead contact fields (spec §18 Commercial).
--
-- The §18 qualifying set includes a business email and the visitor's preferred contact
-- method, which the original b2b_leads table (000025) did not have. Add them so the
-- commercial team captures everything Sales needs. Additive + idempotent; existing rows
-- default to null / 'whatsapp'.

alter table b2b_leads
    add column if not exists email text,
    add column if not exists preferred_contact_method text default 'whatsapp';

comment on column b2b_leads.email is 'Business email for the commercial lead (spec §18).';
comment on column b2b_leads.preferred_contact_method is 'How the lead prefers to be contacted (whatsapp|email|call).';
