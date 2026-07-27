# Facility Notifications

Facilities register mobile numbers to be notified about operational events (new order assigned, arrival reminder, SLA risk, issue reply, payout update, daily summary). The notification **service is mock-first and env-gated** — nothing is sent externally by default.

## Runtime modes — `FACILITY_NOTIFICATIONS_MODE`
- `mock` (default): log a `facility_notifications` row (status `mock_logged`, channel `mock`) and show it in the app's notification center. **No external send.**
- `whatsapp`: send via the approved Evolution WhatsApp provider — **only** when `settings.facility_notifications_ready` is true (i.e. Evolution is live-ready). Otherwise it falls back to logging.
- `sms`: reserved for a future SMS provider (no provider yet → never ready → logs only).

Unknown values resolve to `mock` (fail-safe). `settings.validate_facility_notifications_config()` (called in the app lifespan) fails fast only if `whatsapp` is selected without a live Evolution config.

## Service — `services/facility_notifications.py`
Mirrors `services/notifications.py`. Every trigger builds a PII-safe preview, then
logs (mock) or records a live-send intent, and **never raises** into the caller.

Trigger functions (each idempotent, each returns `None`/a logged row):
- `notify_new_order_assigned(facility_id, order_read)` — on booking-confirm auto-assign. Idempotent per (order, type).
- `notify_order_status_updated(facility_id, order_read, *, old_status, new_status)` — dedupe key `{order}:status:{new_status}`.
- `notify_driver_assigned(facility_id, order_read, *, task_type, expected_completion, driver_id)` — dedupe key `{order}:driver:{driver_id}:{task_type}`.
- `notify_internal_issue_reply(facility_id, issue, *, message_id)` — dedupe key `issue:{issue}:reply:{message_id}`.

Every attempt writes a `facility_notifications` row with status `mock_logged | sent | failed | pending`. The notification center reads these; `read_at` tracks read/unread and drives the header unread badge.

### Idempotency
`facility_notifications` gained a `dedupe_key` column with a partial-unique index on `(facility_id, dedupe_key)`. The generic `notify(...)` skips when a row with the same `dedupe_key` already exists, and `create(...)` uses `on conflict … do nothing` — so a status change / driver assignment / issue reply can never be notified twice, even on a race.

### Wiring (where triggers fire)
| Trigger | Fired from |
|---|---|
| `new_order_assigned` | `api/evolution_webhooks.py` (booking confirm → facility auto-assign) |
| `order_status_updated` | `services/facility_orders.py::apply_action` after a status transition |
| `driver_assigned` | `services/facility_drivers.py::assign_order_to_driver` |
| `internal_issue_reply` | `api/internal_facility_issues.py::reply` (public reply only, not internal notes) |

## Contacts
`facility_notification_contacts` holds registered numbers per facility (full number backend-only, masked for display, plus a `notification_types` array). Managed under Settings → Notifications. Subscribable types include `new_order_assigned`, `order_status_updated`, `driver_assigned`, `internal_issue_reply`, `sla_risk`, `issue_response`, `payout_update`, `daily_summary`.

## Message content (privacy)
Examples — never the customer's full address/phone/payment/internal notes:
- *"New LaundryKhalas order assigned: LK-2026-000042. Service: Boutique Clean & Press. Dubai Marina. Open Facility Dashboard for details."*
- *"Order LK-AE-1042 updated: In cleaning. SLA: 24–48h."*
- *"Driver assigned for order LK-AE-1042. Task: facility handoff. Expected completion: Today 6:30 PM."*
- *"LaundryKhalas Operations replied on your facility issue for order LK-AE-1042. Open Facility Dashboard to view the reply."*

See [[facility-privacy-firewall]].

## Status
Mock-first. Five triggers are wired (new order, status update, driver assigned, internal issue reply — plus `sla_risk` available via the generic helper). No live external channel is sent yet: when a live channel becomes ready the `pending` branch is where the provider send is added. See [[facility-driver-operations]] and [[facility-dashboard]].
