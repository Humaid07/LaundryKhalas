# Facility Driver Operations

The Facility Dashboard **Drivers** section is a first-class operational view of the
drivers/runners linked to a facility — who is **Free** vs **On Job**, and which
order/task each is handling. It is separate from **Settings → Teams** (the people
directory): a driver can be both a team member and a `facility_drivers` row, but
Drivers is where live availability and order-task assignment are managed.

## Data model (migration `000023_facility_drivers`)

- **`facility_drivers`** — id, `facility_id`, optional `user_id` (future driver login),
  name, `phone_e164` (backend-only) + `phone_masked`, `role` (`driver|runner|pickup_partner`),
  `status` (11-value CHECK), `vehicle_type`, `area`, `active`, `last_active_at`.
- **`driver_assignments`** — one order task given to a driver: `driver_id`, `order_id`,
  `order_ref`, `task_type` (`pickup|facility_handoff|delivery|return`),
  `service_summary` (PII-safe label only), `status`
  (`assigned|in_progress|completed|cancelled|issue`), `assigned_at`/`started_at`/
  `completed_at`/`expected_completion_at`, `area`, `notes`. A **partial-unique index**
  enforces at most one active (`assigned|in_progress`) assignment per driver.
- **`driver_status_events`** — audit trail of every driver status change.
- **`facility_issues.driver_id`** — links a driver issue (e.g. `driver_no_show`) to a driver.

Migration `000023` seeds 3 demo drivers for the Marina facility; `scripts/seed_facility_data.py`
adds one active assignment so the page shows a Free-vs-On-Job split out of the box.

> Numbering note: `000022` was taken by a concurrent CRM slice (`000022_crm_segments`),
> so the driver schema is `000023`.

## Status derivation (`services/facility_drivers.py`)

Effective status is **derived** (pure, unit-tested) from the stored driver status +
the active assignment:
- `issue` — stored status `issue_reported`.
- `offline` — driver inactive or status `offline`.
- `on_break` — status `on_break`.
- `on_job` — has an active assignment.
- `free` — active driver, no active assignment, not on break/offline, no issue.

`summarize(...)` produces the tile/tab counts (total, free, on_job, pickup, delivery,
on_break, offline, issues).

## Assignment flow — `assign_order_to_driver(...)`

Role-guarded at the API (owner/manager/admin only). Enforces facility ownership of
**both** the driver and the order (cross-facility → `LookupError`), rejects a
double-booked driver (`DriverActionError`), then:
1. creates a `driver_assignments` row,
2. sets the driver status (task-specific, e.g. `handoff_in_progress`) + writes a
   `driver_status_events` row,
3. writes an `order_events` audit row (`event_type='driver_assigned'`) → appears in the
   order timeline,
4. fires a mock-first `notify_driver_assigned` facility notification.

`update_assignment_status(...)` advances/closes a task (freeing the driver when no other
active task remains); `set_driver_status(...)` handles manual availability changes.

## API (all under `/api/facility`, scoped by `require_facility_scope`)

Read (any facility role): `GET /drivers`, `/drivers/summary`, `/drivers/{id}`,
`/drivers/{id}/assignments`. Manage (owner/manager/admin — server-enforced via
`_require_manage`): `POST /drivers`, `PATCH /drivers/{id}`, `PATCH /drivers/{id}/status`,
`POST /driver-assignments`, `PATCH /driver-assignments/{id}/status`,
`POST /orders/{order_id}/assign-driver`.

Every read is `facility_id`-scoped — a facility can never see or assign another
facility's drivers. Driver payloads carry a **masked** phone only and never any
customer PII (CLAUDE.md §7).

## Order detail integration

`GET /api/facility/orders/{id}` now returns `driver_assignment` + `driver` so the order
detail page shows the assigned driver (masked phone, task, expected completion, status)
with a link to the driver detail page.

## Internal dashboard sync

Driver issues are `facility_issues` rows (issue types include `driver_no_show`) with the
new `driver_id` link. They already flow to the internal ops inbox
(`/api/internal/facility-issues`); an ops **public reply** posts back to the facility
thread and fires `notify_internal_issue_reply`.

## Roles

`facility_owner` / `facility_manager` (and platform `admin`) can manage drivers and
assign tasks. `facility_staff` and `facility_driver` are view-only for management
actions — enforced in the backend, not just hidden in the UI.

See [[facility-notifications]] and [[facility-dashboard]].
