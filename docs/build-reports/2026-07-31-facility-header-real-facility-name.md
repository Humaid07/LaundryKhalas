# Build Report — Facility Dashboard header shows the real facility name

**Date:** 2026-07-31

## 1. Task objective
The Facility Dashboard header always displayed the generic placeholder **"Your Facility"**
instead of the logged-in facility's actual name. Make the header show the real,
facility-scoped name coming from the authenticated facility profile — never a hardcoded string.

## 2. What was built
A frontend data-mapping fix. The header already fetched `GET /api/facility/me`, but the API
client mis-typed the response as a flat profile and read `profile.name` — which was always
`undefined` because the backend returns an **envelope** `{ facility: {...}, role }`. The client
now unwraps that envelope, so `profile.name` (and `operating_status`) resolve correctly. Added a
clean loading skeleton, a `title` tooltip for long names, and removed the fake dev placeholder.

## 3. Why
`facilityApi.me()` read `.name` off `{ facility, role }` → always `undefined` → the header fell
through to the literal `"Your Facility"`. The real name was already available server-side; only
the client envelope-unwrapping was missing.

## 4. Root cause (evidence)
- Backend `api/facility.py::facility_me` returns `{"facility": profile, "role": ...}`.
- `facilities_repo.to_profile()` includes a real `name` field, derived from `principal.facility_id`
  (resolved server-side in `deps.require_facility_scope`, never client-supplied — isolation intact).
- Frontend `facilityApi.me()` was `request<FacilityProfile>(...)` and `FacilityHeader` read
  `profile?.name` → undefined → `"Your Facility"`.

## 5. Files modified
- `apps/facility-dashboard/lib/api-client.ts` — `me()` now unwraps `{ facility, role }` → flat
  `FacilityProfile` (tolerant of a bare-profile response; `facility` is null outside supabase mode).
- `apps/facility-dashboard/components/layout/FacilityHeader.tsx` — resolve name once
  (`profile.name` → cached `user.facility_name` → `"Facility Dashboard"`); loading skeleton;
  `title` attribute for long names (kept existing `truncate`).
- `apps/facility-dashboard/lib/auth-context.tsx` — dev principal `facility_name` `"Your Facility"` → `null`
  (no hardcoded placeholder even during the first render).

## 6. Files created
- `docs/build-reports/2026-07-31-facility-header-real-facility-name.md` (this report).

## 7. API endpoints added/changed
None. Reused existing `GET /api/facility/me` (already facility-scoped, PII-safe).

## 8. Database changes
None.

## 9. UI changes
Facility Dashboard top header now renders the live facility name (e.g. the seeded
`FAC-DXB-MARINA` facility's name), a loading skeleton while `/me` is in flight, and a hover
tooltip for truncated long names. Layout, chips, bell, and toggles unchanged.

## 10. Agent / integration changes
None.

## 11. Mock-only / live / deferred
- No live external calls. Name is DB-sourced via the existing backend (dev/test Supabase).
- Deferred: nothing outstanding for this task.

## 12. Tests run
- `npm run typecheck` — **pass** (fixed a react-query v5 discriminated-union `never` narrowing by
  resolving the name once outside the `isLoading` chain).
- `npm run lint` — **pass** (only a pre-existing warning in `app/(app)/orders/page.tsx`, untouched).
- `npm run build` — **pass** (all routes compiled).
- Backend: no change → pytest not required for this task.

## 13. Known limitations
- If the backend runs outside supabase mode, `/me` returns `facility: null`; the header then shows
  the safe fallback `"Facility Dashboard"` (by design). The real environment runs supabase mode.

## 14. Security / privacy notes
`facility_id` is resolved server-side from the authenticated principal, never from a client param,
so no facility can see another's name. The `/me` payload exposes only partner-safe columns
(`to_profile`) — internal rates / quality score remain hidden (CLAUDE.md §7).

## 15. How to verify manually
1. Start backend (:8100, `DATABASE_MODE=supabase`) and facility dashboard (`npm run dev`, :3010).
2. Open http://localhost:3010 → the desktop header shows the real facility name (not "Your Facility").
3. Navigate Overview / Orders / Finance / Settings → the name is consistent (cached 60s).
4. Temporarily rename the facility in DB / seed a long name → header truncates with a hover tooltip
   and does not push the bell/theme/logout icons out of the bar.

## 16. Next recommended step
Optional: reuse the same `facilityApi.me()` name in the mobile brand slot / page titles for full
consistency, and add a small component test asserting the envelope unwrap.
