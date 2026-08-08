# Build Report — Dev-only Facility Switcher

- **Date:** 2026-08-07
- **Design spec:** [[2026-08-07-facility-switcher-dev-design]] (`docs/superpowers/specs/`)

## 1. Task objective
Let a tester view the facility dashboard as any facility during dev/manual
testing, instead of being pinned to the first active facility (Abu Dhabi
Central). No change to production isolation.

## 2. What was built
A facility switcher dropdown in the facility-dashboard header. It lists all
active facilities and, on selection, scopes every subsequent request to that
facility via an `X-Facility-Id` header the backend honors **only when
`REQUIRE_AUTH` is off**.

## 3. Why
The dashboard is single-facility by design (`require_facility_scope` resolves one
facility per session). Switching previously required editing `.env` +
restarting. This adds a safe, dev-gated in-app switch so order landing/routing
can be observed across the 13 seeded facilities.

## 4. Files created
- `apps/whatsapp-agent/tests/test_facility_switcher.py` — 6 tests (TDD).
- `apps/facility-dashboard/components/layout/FacilitySwitcher.tsx` — dropdown.
- `docs/superpowers/specs/2026-08-07-facility-switcher-dev-design.md` — spec.

## 5. Files modified
- `apps/whatsapp-agent/api/deps.py` — `_facility_exists()` helper; dev branch of
  `require_facility_scope` honors a validated `X-Facility-Id` header.
- `apps/whatsapp-agent/api/facility.py` — `GET /api/facility/switchable`.
- `apps/facility-dashboard/lib/auth-token.ts` — `get/setDevFacilityId()`.
- `apps/facility-dashboard/lib/api-client.ts` — inject `X-Facility-Id`;
  `switchableFacilities()` + `SwitchableFacility` type.
- `apps/facility-dashboard/components/layout/FacilityHeader.tsx` — mount switcher.

## 6. API endpoints
- **Added:** `GET /api/facility/switchable` → `[{id,name,city}]` of active
  facilities; returns `[]` when `REQUIRE_AUTH` is on or outside Supabase mode.
- **Changed (behavior):** facility-scoped routes honor `X-Facility-Id` in dev only.

## 7. DB / models
None. No migration.

## 8. UI
- New `FacilitySwitcher` dropdown in the header; self-hides when fewer than 2
  facilities are returned (i.e. production).

## 9. Mock-only / live
- Dev-only: the override + list endpoint are inert when `REQUIRE_AUTH` is on.

## 10. Deferred
- Switcher for authenticated platform admins (considered, not built — dev-only
  was chosen).

## 11. Tests run
- `tests/test_facility_switcher.py` — 6 passed (written first, watched fail).
- Regression: `test_auth_rbac`, `test_facility_privacy_permissions`,
  `test_facility_orders`, `test_facility_order_view`,
  `test_facilities_management` — 74 passed.
- Full suite — see completion summary.
- Frontend: `tsc --noEmit` clean.
- Browser (Playwright): header switched Abu Dhabi Central → TEST Barsha One
  Laundry; `X-Facility-Id` persisted; data re-scoped on reload. PASS.
- Backend manual: `/me` returns default with no header, TEST Marina Express with
  a valid override, and falls back (no 500) on a bogus id.

## 12. Security / privacy notes
- The override is confined to the `not settings.require_auth` branch; the
  authenticated path is unchanged, so a client-supplied facility is never trusted
  in production. `/switchable` returns `[]` under auth, never exposing the list.
- Unknown/invalid override → best-effort `_facility_exists` returns false → falls
  back to the default facility; never raises.

## 13. How to verify manually
1. Facility dashboard on :3010 (dev, auth off), backend on :8100 (Supabase).
2. Header shows a "Dev" facility dropdown; pick a Dubai TEST facility.
3. Page reloads; header + orders/finance/ratings reflect that facility.

## 14. Next recommended step
Resume WhatsApp manual testing: send from an allow-listed number and watch the
order land, then switch facilities to see routing per facility.
