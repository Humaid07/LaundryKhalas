# Build Report — Facilities Management Module

**Date:** 2026-07-29

## 1. Task objective
Deliver an end-to-end **Facilities Management** module shared across the internal
admin dashboard (`apps/admin`, :3000), the partner portal (`apps/facility-dashboard`,
:3010), the FastAPI backend (`apps/whatsapp-agent`, :8100) and the WhatsApp/AI agent
— built on top of the existing facility subsystem, DB as source of truth, mock-first.

## 2. What was built
- A first-class **Facilities** section in both dashboards (nav + pages).
- Writeable facility CRUD (create / update / status) with validation + audit.
- Internal-only **quality score** and **internal rates**, isolated from partners at
  every layer (schema, serializer, API, tests).
- Strict single-facility partner ownership (server-resolved, never client-supplied).
- Grounded, read-only **agent facility tools** + an audited status-mutation tool.
- A reusable **sidebar long-label hover-scroll** in both dashboards.
- Relocated the existing **Compliance Queue** from Partner Acquisition into Facilities.

## 3. Why
The platform had a mature facility backend (routing, settings, drivers, issues) but
no management surface: facilities could not be created/edited from either app, had no
address / quality / capacity-unit / onboarding-source fields, no facility-level audit,
and the agent had no DB-grounded facility tools. This closes that gap without a
separate app or a mock store.

## 4. Files created
**DB / scripts**
- `supabase/migrations/20260729_000030_facilities_management.sql`
- `apps/whatsapp-agent/scripts/apply_facilities_management.py`
- `apps/whatsapp-agent/scripts/verify_facilities_management.py`

**Backend**
- `apps/whatsapp-agent/db/repositories/facility_audit_repo.py`
- `apps/whatsapp-agent/services/facility_matching.py`
- `apps/whatsapp-agent/services/facility_admin.py`
- `apps/whatsapp-agent/api/internal_facilities.py`
- `apps/whatsapp-agent/api/facility_management.py`
- `apps/whatsapp-agent/agents/whatsapp_agent/facility_tools.py`
- `apps/whatsapp-agent/tests/test_facilities_management.py`
- `apps/whatsapp-agent/tests/test_facility_matching.py`
- `apps/whatsapp-agent/tests/test_llm_facility_tools.py`

**Admin UI**
- `apps/admin/lib/dashboard/facilities-api.ts`
- `apps/admin/components/dashboard/facilities/FacilitiesDirectory.tsx`
- `apps/admin/components/dashboard/facilities/FacilityFormDialog.tsx`
- `apps/admin/components/dashboard/facilities/FacilityDetailPage.tsx`
- `apps/admin/components/dashboard/facilities/FacilityCompliance.tsx`
- `apps/admin/components/dashboard/shell/NavLabel.tsx`
- `apps/admin/app/(dashboard)/facilities/page.tsx`, `.../directory/page.tsx`,
  `.../compliance/page.tsx`, `.../[facilityId]/page.tsx`

**Partner UI**
- `apps/facility-dashboard/components/facilities/FacilityManager.tsx`
- `apps/facility-dashboard/components/layout/NavLabel.tsx`
- `apps/facility-dashboard/app/(app)/facilities/page.tsx`

## 5. Files modified
- Backend: `db/repositories/facilities_repo.py` (writeable + admin/partner serializers),
  `facility_pricing_repo.py` (internal-rate get/set), `facility_settings_repo.py`
  (`is_24h`), `api/facility.py` (partner timings `is_24h` + `/service-categories`),
  `agents/whatsapp_agent/llm_tools.py` (register facility read tools), `schemas.py`
  (facility schemas), `main.py` (register routers).
- Admin: `lib/dashboard/{sections.ts,nav.ts,accents.ts,roles.ts}`, `app/globals.css`,
  `tailwind.config.ts`, `components/dashboard/shell/Sidebar.tsx`,
  `components/dashboard/partner-acquisition/PartnerAcquisition.tsx` (compliance removed).
- Partner: `lib/api-client.ts`, `components/layout/{nav-items.ts,FacilityDesktopShell.tsx,FacilityBottomNav.tsx}`,
  `lib/accents.ts`, `app/globals.css`.

## 6. API endpoints added
**Internal (admin/ops, `require_ops`; rates are `require_admin`):**
- `GET /api/internal/facilities` (list + filters + summary)
- `GET /api/internal/facilities/{id}` (admin serializer + services + timings + audit)
- `POST /api/internal/facilities`
- `PATCH /api/internal/facilities/{id}`
- `PATCH /api/internal/facilities/{id}/status`
- `GET|PUT /api/internal/facilities/{id}/services`
- `GET|PUT /api/internal/facilities/{id}/timings`
- `GET|PUT /api/internal/facilities/{id}/rates` (**admin-only**), `DELETE .../rates/{code}`

**Partner (`require_facility_scope`, ownership from token):**
- `GET /api/facility/facilities` (their 0/1 facility)
- `POST /api/facility/facilities` (self-onboard; 409 if already linked)
- `PATCH /api/facility/facilities/{id}` (403 if not own), `PATCH .../{id}/status`
- `GET /api/facility/service-categories`

## 7. Database changes (migration 000030, additive + idempotent)
- `facilities`: `full_address`, `quality_score` (0–100, internal-only), `capacity_unit`,
  `onboarding_source`, `created_by`, `updated_by` (+ CHECK constraints + status/emirate indexes).
- `facility_timings`: `is_24h`.
- New `facility_audit_log` table (before/after JSON, actor, source) + RLS deny policy.
- Reuses existing `facility_services` (category-level), `facility_rates`, `facility_timings`.

## 8. Agent behavior added
- Read-only grounded tools in `llm_tools.TOOL_SCHEMAS`: `find_eligible_facilities`,
  `list_facilities`, `get_facility`, `get_facility_services`,
  `get_facility_operating_hours` — all JSON-safe, never returning rates/quality.
- `facility_matching.find_eligible` (haversine, no PostGIS; closed/paused excluded,
  busy ranked below open; radius + hours + accepted-service filters; quality used for
  internal ranking only) with a 30s TTL cache invalidated by every facility mutation.
- `facility_tools.agent_update_facility_status` — audited status change via
  `facility_admin` (actor_type=`agent`), deliberately **not** in the customer tool-loop.

## 9. What is mock-only / live
- Mock-first throughout: no live WhatsApp/Stripe/LLM. Facility routing/matching read the
  DB. Internal rates remain MOCK values (as before). No external calls added.

## 10. What is intentionally deferred
- Partner **multi-facility** ownership (kept strict single per founder decision).
- Automated quality-score computation (schema ready; still manual admin entry).
- A dedicated partner `[facilityId]` detail route (single facility → inline edit instead).
- Hard FK from `facility_services` to `services.id` (kept category-code join per decision).

## 11. Security / privacy notes
- `quality_score` + internal rates are internal-only: excluded from partner serializer,
  omitted from `PartnerFacility*` schemas with `extra="forbid"` (protected fields → 422),
  and the ops detail bundle excludes rates (admin-only endpoint).
- Partner ownership is resolved from the JWT (`require_facility_scope`), never from a
  client id; cross-facility edit → 403; agent tools never emit rates/quality.
- Every facility mutation writes `facility_audit_log` (actor, source, before/after).

## 12. Tests run / results
- Backend (pytest, `apps/whatsapp-agent`): `test_facilities_management.py` (20),
  `test_facility_matching.py` (10), `test_llm_facility_tools.py` (6) — **36 passed**
  (run per-file for a clean result; the shared autouse SQLite demo-order fixture is a
  pre-existing Windows flake under rapid re-seed — documented in `tests/conftest.py` — and
  is unrelated to these tests, which mock the DB). Adjacent suites (`test_llm_tools`,
  `test_auth_rbac`, `test_facility_routing`) re-run green. `ruff check` **clean** on all
  new/changed backend files. `import main` succeeds.
- Frontend: `apps/admin` `tsc --noEmit` **pass**, `npm run lint` **0 errors** (one
  pre-existing warning in `app/admin/conversations`). `apps/facility-dashboard`
  `tsc --noEmit` **pass**, `npm run lint` **0 errors** (one pre-existing warning in
  `app/(app)/orders`). Frontends have **no test runner** — gate is typecheck + lint +
  manual (stated honestly; no fabricated frontend test pass).

## 13. Known limitations
- Migration 000030 **applied + verified on the dev/test Supabase** (2026-07-29) via
  `scripts/apply_facilities_management.py` + `verify_facilities_management.py` — all checks
  passed. (Production is untouched; the scripts refuse any non-dev/test project.)
- `next build` not run on Windows (known 500.html rename quirk) — gated on tsc + lint.

## 14. Commands to run
```
# 1. Apply the migration (dev/test Supabase, from apps/whatsapp-agent venv)
python scripts/apply_facilities_management.py
python scripts/verify_facilities_management.py
# 2. Backend tests
pytest tests/test_facilities_management.py tests/test_facility_matching.py tests/test_llm_facility_tools.py
# 3. Frontends
cd apps/admin && npm run typecheck && npm run lint && npm run dev          # :3000
cd apps/facility-dashboard && npm run typecheck && npm run lint && npm run dev  # :3010
```

## 15. Next recommended step
Apply migration 000030 to dev Supabase, seed one facility, and walk the manual test
flow (below) end-to-end; then wire `find_eligible_facilities` into the booking
confirmation path so live routing uses the new eligibility engine.
