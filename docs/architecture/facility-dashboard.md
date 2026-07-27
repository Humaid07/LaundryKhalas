# Facility (Laundry Partner) Dashboard — Architecture

A **separate** mobile-first app for laundry partner facilities, distinct from the internal admin dashboard. Same architecture as the rest of the platform: **Frontend → FastAPI (`apps/whatsapp-agent`) → Supabase/Postgres**. The frontend never touches Supabase directly.

## Apps
- `apps/facility-dashboard` — the partner app (Next.js 15 / React 19 / Tailwind / Recharts), port **3010**. Mobile-first (bottom nav), desktop-compatible (sidebar). Reuses the admin design system (design tokens, `ui/*` + `minimal/*` components, themed charts).
- `apps/admin` — unchanged internal dashboard, plus a facility-issue surface (Operations → Facility Facing).
- `apps/whatsapp-agent` — the one FastAPI backend serving both dashboards.

## Data model (Supabase, migrations 000016–000020)
- `facilities` (+ `orders.facility_id`) — first-class facility; `payout_rate` placeholder (rates fed later).
- `users` — facility roles + `facility_id` scope.
- `facility_issues` + `facility_issue_messages` — facility-raised issues with a threaded conversation.
- `facility_notifications` + `facility_notification_contacts`.
- `facility_settings` / `facility_timings` / `facility_blackout_dates` / `facility_team_members` / `facility_price_change_requests`.

## Auth & per-facility scoping
Facility users authenticate against FastAPI (`/api/auth/login`); their `facility_id` is a JWT claim. `api/deps.py::require_facility_scope` guards every facility endpoint and resolves the caller's `facility_id`; **every facility query filters by it in application SQL** (the service role bypasses RLS, so isolation is enforced in code + tests, never by a client-supplied id). In dev (`REQUIRE_AUTH=false`) an anonymous caller is scoped to the seeded facility so the app is usable without login. See [[facility-privacy-firewall]].

## Order assignment (auto-routing)
When a customer **confirms** a WhatsApp booking, `services/facility_routing.py` auto-assigns the order to a facility (`facilities_repo.select_for_location` → `orders_repo.set_facility`, idempotent via a `facility_id is null` guard) and writes a `facility_assigned` audit event, then mock-notifies the facility (`notify_new_order_assigned`). Selection ranking: location match **area > city > emirate**, then `open` over `busy` (never `closed`/`paused`/inactive), then spare `capacity_daily`, then least-loaded. If no active facility can take work the order is **left unassigned** for ops — nothing is force-routed and no data is invented. Routing **never raises** into the booking flow. Reassignment is ops-only (not automated). See [[2026-07-27-facility-auto-assign-and-notify]].

## Order lifecycle (facility-controlled subset)
Facilities can only advance facility-relevant statuses (`services/facility_orders.py`): accept → mark_received (`picked_up`) → start_cleaning (`in_cleaning`) → move_to_qc → mark_ready (`ready_for_delivery`) → confirm_handoff (`out_for_delivery`). Cancel / refund / price-change / mark-complete / reassign are **forbidden** (backend-rejected). Every action writes an `order_events` audit row.

## Finance
Customer order value attributed to the facility (`orders.estimated_total`, via `services/money.py`), grouped by day/week/month over `confirmed_at`/`created_at`, excluding demo + non-revenue statuses. Service mix is derived from `orders.line_items` joined to the catalogue (`service_items`→`service_categories`) — **never hardcoded**. Facility **payout is deferred**: reported as `pending_rate` (no payout invented) until facility rates are configured.

## Issues → internal dashboard
A facility issue is stored in `facility_issues` and surfaced in the internal dashboard via `/api/internal/facility-issues` (Operations → Facility Facing → Issues tab + a threaded detail page). Internal replies (`sender_type='internal'`, optional `is_internal` notes) appear back in the facility's issue thread. See [[facility-notifications]].

## Key files
- Backend: `api/facility.py`, `api/internal_facility_issues.py`, `db/repositories/facility_*_repo.py`, `services/facility_orders.py`, `services/facility_notifications.py`, `api/deps.py` (`require_facility_scope`).
- Frontend: `apps/facility-dashboard/` (app routes + `components/` + `lib/api-client.ts`).
- Internal: `apps/admin/components/dashboard/operations/FacilityFacing.tsx` + `.../facility-issue-detail/`.
