# Facility Switcher (dev-only) — Design

- **Date:** 2026-08-07
- **Status:** Approved (pending written-spec review)
- **Scope:** Facility dashboard (`apps/facility-dashboard`) + backend guard (`apps/whatsapp-agent`)

## Problem

The facility dashboard is single-facility by design: `require_facility_scope`
(`api/deps.py`) resolves exactly one `facility_id` per session. In dev
(`REQUIRE_AUTH` off, no `FACILITY_DEV_ID`) it always falls back to the first
active facility (Abu Dhabi Central), so a tester cannot view how orders land and
route into the other 12 seeded facilities without editing `.env` and restarting.

We want an in-dashboard switcher to move between all facilities **during dev
testing only**, with **zero change to production isolation**.

## Non-goals (YAGNI)

- No switcher in production / authenticated sessions.
- No cross-facility aggregate view.
- No persistent server-side "current facility" state.
- No change to how authenticated facility users are scoped.

## Security boundary (the load-bearing constraint)

The guard comment is explicit: isolation is enforced server-side and must
**never** trust a client-supplied `facility_id` in a real session. Therefore the
override is honored **only** in the `not settings.require_auth` branch. When
`REQUIRE_AUTH` is on, behavior is byte-for-byte unchanged: facility users stay
locked to their own `facility_id`; admins keep the existing `?facility_id=`
support. The dev-only list endpoint returns `[]` when auth is on, so the full
facility list is never exposed in production.

## Design

### Backend

**1. `require_facility_scope` (`api/deps.py`) — dev branch only.**
Inside `if not settings.require_auth:`, before falling back to
`_dev_facility_id()`, read an optional `X-Facility-Id` request header. If it is a
non-empty value that matches an existing facility row
(`select exists(select 1 from facilities where id = $1)`), use it. Otherwise use
the current `_dev_facility_id()` fallback. Invalid/unknown ids are ignored (fall
back), never 500. The `require_auth`-on path is untouched.

**2. New endpoint `GET /api/facility/switchable` (facility router).**
Returns `[{ id, name, city }]` for active facilities ordered by `created_at`,
**only when `settings.require_auth` is false**; returns `[]` otherwise. This
feeds the dropdown and self-disables in production. Uses the existing service
role DB access; no new table.

### Frontend (`apps/facility-dashboard`)

**3. `lib/api-client.ts` — single injection point.**
In `request()` and `requestForm()`, if `localStorage` holds a selected
`facility_id` (key e.g. `lk.dev.facilityId`), attach it as the `X-Facility-Id`
header on every call. Guarded by `typeof window !== "undefined"`.

**4. New client call + type.**
`fetchSwitchableFacilities(): Promise<{ id: string; name: string; city: string }[]>`
hitting `/api/facility/switchable`.

**5. `components/layout/FacilityHeader.tsx` — the dropdown.**
A compact `<select>`/menu listing switchable facilities, showing the current one
as selected (derived from stored id, falling back to `/api/facility/me`). Hidden
when the list is empty (production). On change: write `localStorage`, then
`window.location.reload()` so all react-query data refetches under the new
facility. Full reload chosen for guaranteed-correct refetch (dev tool).

## Data flow

```
pick facility in header dropdown
  -> localStorage[lk.dev.facilityId] = id
  -> window.location.reload()
  -> every api-client request sends  X-Facility-Id: <id>
  -> require_facility_scope (dev branch) validates id -> scopes queries
  -> all pages render the selected facility
```

## Error handling

- Unknown/blank `X-Facility-Id` in dev: silently falls back to default facility.
- `/api/facility/switchable` when auth on: returns `[]`, dropdown hides.
- Backend unreachable: existing `FacilityApiError(0, ...)` path unchanged.

## Testing

- Backend: unit test `require_facility_scope` — (a) dev + valid header → that
  facility; (b) dev + bogus header → default fallback; (c) `require_auth` on +
  header present → header ignored (locked to own facility). Test
  `/api/facility/switchable` returns list in dev, `[]` when auth on.
- Frontend: `tsc --noEmit` + manual — switch across a few facilities, confirm
  orders/ratings/finance pages all reflect the selected facility and the header
  shows the right name.

## Files touched

- `apps/whatsapp-agent/api/deps.py` (guard, dev branch)
- `apps/whatsapp-agent/api/facility.py` (new `/switchable` endpoint)
- `apps/facility-dashboard/lib/api-client.ts` (header injection + fetch fn + type)
- `apps/facility-dashboard/components/layout/FacilityHeader.tsx` (dropdown)
- Backend test file for the guard/endpoint.

## Rollout

Dev-only behavior; no migration. Safe to run with `REQUIRE_AUTH` on in
production — switcher and override both inert.
