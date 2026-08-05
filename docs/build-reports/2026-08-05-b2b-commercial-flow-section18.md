# Build Report — B2B Commercial Sales-Quote Flow (Section 18 Commercial)

**Date:** 2026-08-05
**Status:** Existing B2B flow audited + extended for §18; full-suite verification in progress.
UNCOMMITTED.

## 1. Objective
Section 18 (Commercial / B2B). An audit found the flow already largely built by the prior
hardening program: `services/b2b.py` (classification + safe acknowledgement, no pricing
promises), `db/repositories/b2b_leads_repo.py` + migration `000025` (b2b_leads lead entity),
`crm_segments` b2b_lead tier, and webhook escalation routing B2B → its own lead entity + the
Sales / Partner Acquisition team (never the consumer funnel, never consumer pricing). This
increment closes the remaining §18 gaps.

## 2. What changed
- **Airbnb business type** — added to `BUSINESS_TYPES` + keyword classifier, plus
  `may_use_consumer_pricing(business_type)` → True only for Airbnb (a small Airbnb requirement
  may use the standard consumer service when the volume genuinely fits; every other commercial
  type is priced by Sales). The acknowledgement adds the Airbnb "small requirement → standard
  service" note.
- **Fuller qualifier collection** — `acknowledgement` now asks for company name, business email,
  services, approximate weekly volume, collection frequency, and location (still no price, no
  terms). `QUALIFYING_FIELDS` enumerates the full §18 set (first name, business name, email,
  contact number, required services, estimated weekly volume, volume unit, frequency, location,
  preferred contact method).
- **Trial-collection stance** — `trial_note()`: small trials may be free, a larger trial may be
  chargeable — never promises a free large-volume trial.
- **Lead schema** — migration `000044` adds `email` + `preferred_contact_method` to `b2b_leads`;
  `b2b_leads_repo._COLS` + `_UPDATABLE` extended so they persist.

## 3. Files
**Modified:** `services/b2b.py`, `db/repositories/b2b_leads_repo.py`, `tests/test_b2b.py`.
**Created:** `supabase/migrations/20260805_000044_b2b_leads_contact_fields.sql`.

## 4. Tests
- `tests/test_b2b.py` — Airbnb classification, `may_use_consumer_pricing` (Airbnb yes / others
  no), `QUALIFYING_FIELDS` coverage, `trial_note` (no free large trial), enriched ack (email +
  Airbnb note). Existing routing / no-price / whitelist guards still pass (16 total).
- Full-suite regression: appended.

## 5. Kept from the existing flow (unchanged, already §18-aligned)
- B2B detection → its own lead entity, never the consumer pickup funnel / conversion metrics.
- All commercial pricing routed to Sales; the auto-ack never quotes a price or promises terms.
- Lead stored in `b2b_leads` (dashboard: Sales / Partner Acquisition) — no external CRM.

## 6. Deferred
- Same-working-day sales-response-target SLA wording (currently the lead is queued to Sales; the
  "before close of business, no impossible after-hours promise" nuance is a Sales-ops process,
  not agent copy).
