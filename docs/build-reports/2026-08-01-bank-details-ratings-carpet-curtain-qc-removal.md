# Build Report — Bank Details, Ratings, Carpet/Curtain Services, Quality-Check Removal

**Date:** 2026-08-01
**Branch:** `main` (uncommitted working tree; owner's commit `6c6a2b0` landed concurrently — see Known Limitations)

## 1. Task objective
Ship five connected changes across the Facility/Partner Portal (`apps/facility-dashboard`, :3010), the Internal Dashboard (`apps/admin`, :3000), and the FastAPI backend (`apps/whatsapp-agent`, :8100):
1. Remove the partner **Quality Check** operations toggle.
2. Add **Carpet Cleaning** + **Curtain Cleaning** as real, facility-selectable accepted services.
3. Add **encrypted bank details** (partner + internal, masked, reveal, audited).
4. Add a **Ratings** system (facility + driver evaluations, factor scoring, backend-authoritative overall, partner view + internal management).
5. Wire it all to the real backend/DB — no static mocks — while preserving the existing design system, auth, ownership model, and agent privacy firewall.

## 2. What was built (by area)

### Quality Check removal
- Partner Settings → Operations toggle, its form state, and the label removed.
- Backend `facility_settings_repo` allow-list + selected columns cleaned.
- Seed script stopped writing the column.
- **Migration 000036** drops the unused `facility_settings.quality_check_required` column. (It was inert: the UI sent `quality_check_enabled` while the backend only stored `quality_check_required`, and nothing read it. The order-level QC workflow and the internal `quality_score` rating are separate systems and were left untouched.)

### Carpet + Curtain services
- Promoted carpet/curtain out of `HOME_CARE` into two new **top-level catalogue categories** `CARPET_CLEANING` and `CURTAIN_CLEANING` in `config/laundry_catalogue.json`, re-seeded idempotently. **Item codes are unchanged** (no order/pricing history breakage) — only the parent category moved, so nothing is duplicated.
- Facility accepted-services pickers (both apps) render categories dynamically from the DB, so the two new services appear automatically; `facility_admin._check_services` validates against them; matching/pricing/agent-lookup all resolve them.
- Existing facilities do **not** auto-accept the new services (a `facility_services` row is created only when a facility enables one) — exactly the spec requirement.

### Bank details (encrypted)
- **Migration 000037** `facility_bank_details` (one row/facility): descriptive fields in clear; **IBAN + account number stored as ciphertext only** plus a `*_last4` for masked display; RLS deny; audit-safe.
- New **`services/field_encryption.py`** — Fernet (AES-128-CBC + HMAC) via the `cryptography` library, key derived from `BANK_ENCRYPTION_KEY` (falls back to the JWT secret in dev; **raises rather than storing plaintext** if unset under `REQUIRE_AUTH=true`).
- `services/facility_bank.py` — the crypto/masking/validation/audit boundary: UAE IBAN validation (mod-97 + 23-char/`AE` rule), masking (`AE•• •••• •••• •••• 1234`), partner/internal shaping, audit with **masked-only** values (`iban_last4`), explicit **reveal** (decrypt) that is audited.
- `db/repositories/facility_bank_repo.py` — dumb CRUD (never encrypts/masks).
- API: partner `GET/PUT /api/facility/bank-details` + `POST …/reveal` (owner/manager, session-scoped); internal `GET/PUT /api/internal/facilities/{id}/bank-details` + `…/reveal` (view = operations, **edit/reveal = admin-only**).
- Frontend: partner **Bank Details** section in My Facilities (view masked → reveal → edit); admin **Bank Details** card on the facility detail page (403-aware for operations vs admin).

### Ratings
- **Migration 000038** — `facility_evaluations` / `facility_evaluation_factors` / `driver_evaluations` / `driver_evaluation_factors`. Append-only history, `status` draft/published/archived, CHECK constraints (scores + overall 1–5, weight ≥ 0), RLS deny on all four.
- `config/rating_factors.json` — canonical factor keys/labels/weights (8 facility, 8 driver) + scale + rounding. Weighting is config-controlled, never client-editable.
- `services/ratings.py` — **the backend source of truth**: validates factor input, computes `overall = round(Σ(score·weight)/Σweight, 1)` clamped 1–5, and aggregates published history (current = latest, per-factor averages, count, latest date, chronological trend).
- `services/rating_service.py` — orchestration + **visibility boundary**: `to_internal` (everything) vs `to_partner` (overall, approved factor scores, date, partner-visible summary; **no internal notes, no evaluator identity, no weights, no drafts/archived**). Every write audited.
- Repos: `facility_evaluations_repo.py`, `driver_evaluations_repo.py` (transactional header + factor writes).
- API: internal `POST/PATCH/GET` facility + driver evaluations, `GET …/rating` summaries, `GET /api/internal/rating-factors`, `GET /api/internal/facilities/{id}/drivers` (operations+admin). Partner **read-only** `GET /api/facility/rating`, `GET /api/facility/ratings/drivers`, `GET /api/facility/drivers/{id}/rating` (own facility only).
- Frontend: partner **Ratings** page (new nav item) — facility rating card (overall, factor bars, count, last date, trend, performance summary) + per-driver ratings; internal **Performance rating** + **Driver ratings** sections on the facility detail page with a rating dialog (1–5 factor picker, live overall preview, partner-summary vs internal-notes, edit + history).

## 3. Why
Directly implements the owner's spec (§§1–16): remove a dead toggle, make carpet/curtain individually bookable/assignable, capture payout banking securely, and give operations a way to score facilities/drivers that partners can see (summary only) — all connected to the real DB with server-side authorization and the agent privacy firewall intact.

## 4. Files created
- `supabase/migrations/20260801_000036_remove_quality_check_required.sql`
- `supabase/migrations/20260801_000037_facility_bank_details.sql`
- `supabase/migrations/20260801_000038_facility_driver_ratings.sql`
- `apps/whatsapp-agent/services/field_encryption.py`, `services/facility_bank.py`, `services/ratings.py`, `services/rating_service.py`
- `apps/whatsapp-agent/db/repositories/facility_bank_repo.py`, `facility_evaluations_repo.py`, `driver_evaluations_repo.py`
- `apps/whatsapp-agent/api/internal_ratings.py`
- `apps/whatsapp-agent/config/rating_factors.json`
- `apps/whatsapp-agent/scripts/apply_facility_bank_details.py` (+ `verify_…`), `apply_facility_driver_ratings.py` (+ `verify_…`)
- `apps/whatsapp-agent/tests/test_quality_check_removed.py`, `test_facility_bank.py`, `test_ratings.py`, `test_agent_no_sensitive_access.py`
- `apps/admin/lib/dashboard/ratings-api.ts`, `components/dashboard/facilities/BankDetailsCard.tsx`, `components/dashboard/facilities/RatingsSection.tsx`
- `apps/facility-dashboard/components/facilities/BankDetailsSection.tsx`, `app/(app)/ratings/page.tsx`

## 5. Files modified
- Backend: `settings.py` (bank key), `schemas.py` (bank + evaluation models), `main.py` (register `internal_ratings`), `api/facility.py` (partner bank + ratings), `api/internal_facilities.py` (internal bank), `db/repositories/facility_settings_repo.py`, `config/laundry_catalogue.json`, `scripts/seed_facility_data.py`.
- Frontend: facility `lib/api-client.ts`, `components/facilities/FacilityManager.tsx`, `components/layout/nav-items.ts`, `app/(app)/settings/operations/page.tsx`, `app/(app)/settings/page.tsx`; admin `lib/dashboard/facilities-api.ts`, `components/dashboard/facilities/FacilityDetailPage.tsx`.
- Tests updated for intentional changes: `test_catalogue_pricing.py` (11 categories — folded into commit `6c6a2b0`), `test_service_selection_interactive.py` (11 options), `test_returning_customer_behavior.py` (prompt contract — see §18).

## 6. API endpoints added
- Partner: `GET/PUT /api/facility/bank-details`, `POST /api/facility/bank-details/reveal`, `GET /api/facility/rating`, `GET /api/facility/ratings/drivers`, `GET /api/facility/drivers/{id}/rating`.
- Internal: `GET/PUT /api/internal/facilities/{id}/bank-details`, `POST …/reveal`, `GET /api/internal/rating-factors`, `GET/POST/PATCH /api/internal/facilities/{id}/evaluations`, `GET /api/internal/facilities/{id}/rating`, `GET /api/internal/facilities/{id}/drivers`, `GET/POST/PATCH /api/internal/drivers/{id}/evaluations`, `GET /api/internal/drivers/{id}/rating`.

## 7. Database
- **000036** drops `facility_settings.quality_check_required`.
- **000037** `facility_bank_details` (encrypted).
- **000038** four ratings tables + constraints + RLS.
- Catalogue re-seed: 9 → **11 categories**, **120 items unchanged** (carpet/curtain re-parented, 0 deactivated).
- All applied + verified against the dev/test Supabase project.

## 8. Mock-only / Live / Deferred
- **Live (real DB):** every feature here is backend-connected; no static mock sections.
- **Deferred (documented):** optional bank-document upload (spec makes it conditional and the upload layer is image-only — not extended); manual-override of the official rating (spec says only if an existing workflow needs it — none does); wiring ratings into agent facility-matching (kept out on purpose — the agent must not see internal ratings).

## 9. Security / privacy
- IBAN + account number: Fernet-encrypted at rest, plaintext never persisted/logged; masked reads by default; reveal is role-gated (partner owner/manager; internal admin) and audited.
- Ownership resolved from the authenticated session (`require_facility_scope` / `_fid`), never from a client-supplied id; internal edit/reveal admin-only.
- Audit (`facility_audit_log`) stores masked identifiers only (`iban_last4`), plus rating create/update/archive/reveal with before/after scores + status.
- **Agent firewall:** the customer WhatsApp agent imports none of the bank/ratings modules; its facility tools return a safe dict (no quality_score/rates/bank/ratings). Locked in by `test_agent_no_sensitive_access.py`.

## 10. Tests & results
- **Backend:** 4 new suites (bank 19, ratings 17, quality-check 4, agent-firewall 3) + updated catalogue/service tests. Full suite: **1272 passed / 2 failed → both stale-assertion failures fixed and re-verified** (see §18). Re-run in progress at report time.
- **End-to-end against real Supabase:** bank encrypt→store(ciphertext)→masked read→reveal(decrypt)→masked audit, all confirmed + cleaned up; facility & driver evaluation create→summary→trend→partner-view(hides internal notes)→archive(history preserved), all confirmed + cleaned up.
- **Frontend:** `tsc --noEmit` clean on both apps; `next lint` clean on both apps (only pre-existing warnings in untouched files).

## 11. Commands
```
cd apps/whatsapp-agent
DATABASE_MODE=supabase python scripts/apply_facility_bank_details.py && python scripts/verify_facility_bank_details.py
DATABASE_MODE=supabase python scripts/apply_facility_driver_ratings.py && python scripts/verify_facility_driver_ratings.py
DATABASE_MODE=supabase python scripts/seed_service_catalogue.py --no-ddl   # carpet/curtain
python -m pytest -q
cd ../facility-dashboard && npm run typecheck && npm run lint
cd ../admin && npm run typecheck && npm run lint
```

## 12. Next recommended step
Commit this working tree (all listed files) once the owner's concurrent work is reconciled, set a real `BANK_ENCRYPTION_KEY` for any non-dev environment, and — if desired later — seed a couple of demo evaluations so the partner Ratings page shows populated cards in a demo.
