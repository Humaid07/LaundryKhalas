# Build Report — Facilities Overview + Add-Facility modal redesign

- **Date:** 2026-08-03
- **Area:** Internal admin dashboard (`apps/admin`) + backend (`apps/whatsapp-agent`)
- **Branch/commit:** `main` (uncommitted at time of writing)

## 1. Task objective
Two connected improvements to the internal **Facilities** section:
1. Redesign the **Add Facility** modal — larger, cleaner, premium, properly dimmed
   background, grouped sections, better inputs, pinned actions, field-level validation.
2. Split **Facilities → Overview** from **Facilities → Directory** (they were the same
   page). Overview becomes a real facility-performance/insights page; Directory stays the
   list.

## 2–5. What was built & why
- **Add Facility modal** now uses a strong dark overlay (`bg-ink/75 backdrop-blur-md`) so
  the page behind is no longer readable, is centred and wider (`sm:max-w-[960px]`,
  `max-h-[88vh]` with an internal scroll), has a **pinned footer** (Cancel / Add facility
  stay visible), groups fields into four labelled sections (Basic details / Location &
  coverage / Operations / Services), taller `h-11 rounded-xl` inputs with an orange focus
  ring, an orange primary button (Facilities accent), a **Saving…** loading state, and
  **field-level validation** (inline red messages + red input rings) instead of one generic
  error. Bank details + operating hours are intentionally **not** in the create form — they
  are separate, admin-scoped, post-create flows on the facility detail page, so the modal
  never fake-saves unsupported fields (CLAUDE.md §8/§9).
- **Facilities Overview** is a new metrics page driven by a new **real** aggregation
  endpoint. Every KPI/section is computed from live rows (facilities / orders /
  facility_issues / facility_services); metrics with no backing data return `null` and
  render as “—” / “no data yet” (never invented — CLAUDE.md §7/§9).

## 6. Files created
- `apps/whatsapp-agent/db/repositories/facility_overview_repo.py` — fleet aggregation SQL
  (per-facility metrics, avg completion, service coverage).
- `apps/whatsapp-agent/services/facility_overview.py` — assembles KPIs + rankings from the
  repo rows (pure, honest nulls).
- `apps/whatsapp-agent/tests/test_facility_overview.py` — 10 tests (assembly logic + repo
  SQL scoping + endpoint guard).
- `apps/admin/components/dashboard/facilities/FacilitiesOverview.tsx` — the Overview UI.
- `apps/admin/app/(dashboard)/facilities/overview/page.tsx` — the `/facilities/overview` route.

## 7. Files modified
- `apps/admin/components/dashboard/facilities/FacilityFormDialog.tsx` — modal redesign.
- `apps/admin/lib/dashboard/facilities-api.ts` — `getFacilitiesOverview()` + overview types.
- `apps/admin/lib/dashboard/sections.ts` — added the `overview` subsection.
- `apps/admin/lib/dashboard/nav.ts` — Facilities now uses `childrenOf` (no synthetic
  "Overview" child, since Overview is now a real subsection → no duplicate sidebar link).
- `apps/admin/app/(dashboard)/facilities/page.tsx` — base route redirects to
  `/facilities/overview` (the canonical first view).

## 8. API endpoints added/changed
- **`GET /api/internal/facilities/overview`** (guard `require_ops`; Supabase-gated;
  declared **before** `/{facility_id}` so "overview" is not captured as a facility id).
  Query params: `city, emirate, status, service, days` (days ≤ 0 → all-time; default 30).
  Response: `{ kpis, most_active_facilities, most_completed_facilities, standout_by_city,
  attention_facilities, service_coverage, filters_applied }`.

## 9. Database
No schema/migration changes. All metrics read existing columns/tables
(`orders.facility_id/status/completed_at/confirmed_at/estimated_delivery_end_at`,
`facility_issues`, `facility_services`, `facilities.capacity_daily/quality_score`).

## 10. UI pages/components
- New `FacilitiesOverview` (KPI band, most-active, most-completed, standout-by-city,
  attention, service-coverage, filters + period).
- Redesigned `FacilityFormDialog`.
- Directory unchanged.

## 11–12. Agent / integrations
None.

## 13. What is mock-only
Nothing new is mocked. The endpoint returns empty-but-shaped data when not in Supabase mode.

## 14. What is live
The Overview endpoint runs against the dev/test Supabase project and returns real
aggregates (verified live — see §17).

## 15. Intentionally deferred
- Bank details + operating hours in the **create** modal (managed post-create on the detail
  page).
- Rating/quality in the Overview KPIs (facility_evaluations/quality_score are unseeded; the
  card fields exist and will populate once ops author evaluations).

## 16–17. Tests run & results
- Backend: `pytest tests/test_facility_overview.py -q` → **10 passed**.
- Admin: `npm run typecheck` → **0 errors**; `npm run lint` → **exit 0**;
  `npm run build` → (see §18).
- Live: `GET /api/internal/facilities/overview?days=30` returned real data
  (2 facilities, in_progress=10, completed=1, utilisation 6.25%, issues=1,
  `avg_completion_seconds: null` = honest "no data yet").

## 18. Known limitations / notes
- `next build` on Windows can spuriously fail on the 500.html rename **when the dev server
  is running** (documented repo quirk); tsc + lint + runtime dev verification are the
  authoritative gates here.
- `avg_completion_seconds` / `avg_utilisation` are `null` until there are completed orders
  (with confirmed_at) / facilities with capacity set — shown as “—”, never faked.
- Service-coverage legitimately shows 0 for categories no facility offers yet (a real gap,
  highlighted in red).

## 19–20. Security / privacy
- Endpoint is `require_ops` (internal). Only safe internal facility fields are returned
  (name/code/city/area/status/counts/quality). No customer PII, no payout/margin, no bank
  data. `quality_score` is internal-only and only surfaced on this internal endpoint.

## 21. Cost/LLM
None (no LLM calls).

## 22. Screens to demo
Facilities → Overview (KPIs + rankings + coverage); Facilities → Directory → **Add facility**
(new modal).

## 23. Commands
```
# backend tests
cd apps/whatsapp-agent && ./.venv/Scripts/python.exe -m pytest tests/test_facility_overview.py -q
# admin gates
cd apps/admin && npm run typecheck && npm run lint && npm run build
```

## 24. Manual verification
1. Open http://localhost:3000 → Facilities (redirects to Overview).
2. Confirm Overview shows KPIs + most-active + most-completed + standout-by-city +
   attention + service-coverage, and the filters/period work.
3. Facilities → Facilities Directory → still the list/search/cards.
4. Click **Add facility** → modal is larger, background dimmed, sections grouped, inputs
   comfortable, footer pinned; invalid lat/long shows inline errors; save shows “Saving…”.
5. Check mobile width — single column, no horizontal overflow.

## 25. Next recommended step
Wire the Overview period/filters into the sidebar global-filter system if/when Facilities
becomes a globally-filterable section; seed a few `facility_evaluations` so the quality
columns populate.
