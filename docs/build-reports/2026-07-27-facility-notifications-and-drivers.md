# Build Report — Facility Notifications & Drivers Section

- **Date:** 2026-07-27
- **Module:** Facility (partner) Dashboard
- **Status:** Backend complete + tested (mock-first); frontend Drivers section + notification wiring added. Uncommitted.

## 1. Objective
Two additions to the Facility Dashboard:
1. **Automatic facility mobile notifications** when an order is assigned/updated, a driver is assigned, or Operations replies to an issue — **mock-first and env-gated** (no live WhatsApp/SMS unless explicitly enabled).
2. A separate **Drivers** section (its own sidebar/mobile-nav route) for live driver availability and order-task assignment — not buried in Settings → Teams.

## 2. What was built / why
The notification tables, contacts CRUD, mock-first service, notification center, and the single `new_order_assigned` trigger already existed from prior facility work. This build **added the remaining triggers + wiring** and the **entire driver domain** (schema, repos, service, API, UI), because drivers are operational and the facility team needs at-a-glance Free/On-Job visibility and order→driver assignment.

## 3. Files created
**Backend**
- `supabase/migrations/20260727_000023_facility_drivers.sql` — `facility_drivers`, `driver_assignments`, `driver_status_events`; `facility_issues.driver_id`; `facility_notifications.issue_id` + `dedupe_key`; demo drivers.
- `apps/whatsapp-agent/db/repositories/facility_drivers_repo.py`
- `apps/whatsapp-agent/db/repositories/driver_assignments_repo.py`
- `apps/whatsapp-agent/services/facility_drivers.py`
- `apps/whatsapp-agent/tests/test_facility_drivers.py`

**Docs**
- `docs/architecture/facility-driver-operations.md`
- `docs/checklists/facility-notifications-and-drivers-test-script.md`
- `docs/build-reports/2026-07-27-facility-notifications-and-drivers.md` (this file)

**Frontend** (`apps/facility-dashboard`)
- `app/(app)/drivers/page.tsx` — list: Free/On-Job/Issues tiles, sticky tab row, mobile card stack / desktop 2-col grid, manage-gated add-driver form.
- `app/(app)/drivers/[driverId]/page.tsx` — detail: header, at-a-glance, current assignment (+unassign), recent assignments, issues panel, manage-gated actions + assign modal.
- `components/drivers/`: `DriverStatusBadge.tsx`, `DriverCard.tsx`, `DriverTabs.tsx`, `DriverAssignmentCard.tsx`, `DriverTaskList.tsx`, `DriverDetailHeader.tsx`, `DriverIssuePanel.tsx`, `AssignDriverModal.tsx`.

## 4. Files modified
- `apps/whatsapp-agent/services/facility_notifications.py` — added `notify_order_status_updated`, `notify_driver_assigned`, `notify_internal_issue_reply`, PII-safe previews, dedupe-key support in `notify`.
- `apps/whatsapp-agent/db/repositories/facility_notifications_repo.py` — `issue_uuid` + `dedupe_key` on `create` (on-conflict-do-nothing), `exists_by_dedupe`, extended `_SELECT`.
- `apps/whatsapp-agent/services/facility_orders.py` — `apply_action` fires `notify_order_status_updated` after a status change.
- `apps/whatsapp-agent/api/internal_facility_issues.py` — public reply fires `notify_internal_issue_reply`.
- `apps/whatsapp-agent/api/facility.py` — driver + assignment endpoints, `_require_manage` role gate, order-detail now returns `driver_assignment` + `driver`.
- `apps/whatsapp-agent/scripts/seed_facility_data.py` — seeds one active driver assignment.
- `apps/facility-dashboard`: `components/layout/nav-items.ts`, `FacilityBottomNav.tsx` (grid-cols-5 + More), `FacilityDesktopShell.tsx`; `lib/api-client.ts` (driver types/methods + order-detail `driver_assignment`/`driver` + notification `issue_id`), `lib/status.ts` (driver tones/labels), `lib/roles.ts` (`canManageFacility`); `app/(app)/orders/[orderId]/page.tsx` (driver card + assign); `app/(app)/settings/notifications/page.tsx` (type picker); `components/layout/NotificationCenter.tsx` (per-type icons + issue/order links).
- `docs/architecture/facility-notifications.md`, `docs/presentation-notes/facility-notifications-and-drivers-demo.md`, `docs/00-Home.md`.

### Frontend verification
`npx tsc --noEmit` → **exit 0 (clean)**. `next lint` → no new warnings (one pre-existing `react-hooks/exhaustive-deps` in the untouched orders list page). Final nav: desktop **Home · Orders · Drivers · Finance · Issues · Settings**; mobile bottom **Home · Orders · Drivers · Finance · More**.

## 5. API endpoints added
Under `/api/facility` (scoped by `require_facility_scope`):
- Read (any facility role): `GET /drivers`, `/drivers/summary`, `/drivers/{id}`, `/drivers/{id}/assignments`.
- Manage (owner/manager/admin, server-enforced): `POST /drivers`, `PATCH /drivers/{id}`, `PATCH /drivers/{id}/status`, `POST /driver-assignments`, `PATCH /driver-assignments/{id}/status`, `POST /orders/{order_id}/assign-driver`.
- `GET /orders/{id}` extended with `driver_assignment` + `driver`.

## 6. Database changes
Migration `000023`: `facility_drivers`, `driver_assignments` (partial-unique active-assignment index), `driver_status_events`, `facility_issues.driver_id`, `facility_notifications.issue_id` + `dedupe_key` (partial-unique `(facility_id, dedupe_key)`).

## 7. Notification triggers (min must-haves — all delivered)
`new_order_assigned` (existing), `order_status_updated`, `driver_assigned`, `internal_issue_reply`. Each idempotent (dedupe key), each PII-safe, each never raises. `sla_risk` available via the generic helper.

## 8. Notification modes
`FACILITY_NOTIFICATIONS_MODE=mock|whatsapp|sms` (default **mock**). Mock logs a `mock_logged` row + shows in the center, no external send. `whatsapp` sends only when `facility_notifications_ready`; otherwise falls back to `mock_logged` (never crashes the order flow). `sms` reserved. Live send itself is still a `pending`-status stub — no provider send is wired yet.

## 9. Privacy
Driver + notification payloads carry masked phone / service label / area only — never customer full phone, address, payment, internal notes, or AI reasoning (CLAUDE.md §7). Verified by tests asserting PII strings are absent from previews.

## 10. Mock vs live
- **Mock (default):** notifications logged only; drivers/assignments fully functional against the dev/test Supabase.
- **Live:** no live external notification channel is sent (stubbed `pending`); requires an approved provider + readiness env — intentionally deferred.

## 11. Tests run & results
- `pytest tests/test_facility_drivers.py tests/test_facility_notifications.py` → **20 passed**.
- Full backend suite → **639 passed, 1 error**. The lone error (`test_service_taxonomy_options_endpoint`) is a **pre-existing full-run ordering flake** — it passes in isolation and is unrelated to facility code.
- Frontend `tsc --noEmit` — see §frontend.

## 12. Known limitations / deferred
- Live notification send (WhatsApp/SMS) not wired — mock/`pending` only.
- Facility tables are Postgres-only; unit tests mock the repo layer (matches existing facility test pattern). No SQLite ORM mirror for driver tables.
- Driver login (per-driver auth) deferred (`facility_drivers.user_id` reserved).
- `facility_staff` is view-only for management (no partial-edit tier yet).
- Status-update notifications fire on facility-initiated actions too (acceptable; contacts still want the ping).

## 13. Security/privacy notes
Facility isolation enforced in `require_facility_scope` + every repo query filters `facility_id`; cross-facility driver/order assignment raises `LookupError` (404). Management actions are server-gated by `_require_manage`, not just hidden in the UI.

## 14. How to verify
See `docs/checklists/facility-notifications-and-drivers-test-script.md`.

## 15. Next recommended step
Wire a live notification provider behind the readiness env (replace the `pending` stub) once an approved channel exists; add a `facility_staff` limited-edit tier; optional per-driver login.
