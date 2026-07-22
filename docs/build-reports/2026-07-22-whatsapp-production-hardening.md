# Build Report — WhatsApp Agent Production Hardening (modes, takeover, notifications, expiry)

**Date:** 2026-07-22
**Related:** [[2026-07-22-whatsapp-booking-state-machine]] · [[2026-07-22-orders-vertical-slice]]

## Audit result
Most of the production spec was already delivered (booking FSM, idempotency, TEST allowlist, phone normalization, message persistence, Orders section + cards + detail + timeline, **Open Chat in Operations** deep-link, order-events, demo-guarding, order APIs, 268 tests). **"Laundry Coloss"** — grep found **zero** matches; the repo already uses "LaundryKhalaas", nothing to rename. Genuine gaps: no TEST/LIVE/PAUSED mode with a safe default, no human-takeover gating on the reply path, no status-change customer notification, no draft-expiry, no transition validation, no RBAC.

## What this turn added
1. **Operating modes `WHATSAPP_AGENT_MODE` = test | live | paused** (`settings.agent_operating_mode`, **safe default `paused`**; unknown → paused). `test` replies only to `EVOLUTION_ALLOWED_TEST_NUMBERS`, `live` to all valid numbers, `paused` stores messages and sends nothing. Wired into `api/evolution_webhooks.py`: LIVE skips the allowlist gate; PAUSED stores-only.
2. **Human-takeover gating** — when a conversation is `human_takeover` (or mode paused / replies off), the webhook stores the inbound but **does not run the FSM or reply**, so the AI never talks over an operator. AI resumes when takeover ends.
3. **Status-change → WhatsApp notification** (`services/notifications.py`) fired from `PATCH/POST /api/orders/{id}/status` after commit: idempotent (per order+status), respects mode/allowlist/live-readiness, templated per customer-facing status, logs `NOTIFICATION_SENT|SKIPPED|FAILED` as order_events. A send failure never rolls back the status.
4. **Draft expiry** — `scripts/expire_drafts.py` marks `DRAFT` orders older than `DRAFT_EXPIRY_HOURS` (default 24) as **`abandoned`** (new terminal status), writes `ORDER_ABANDONED` events; idempotent, never deletes, never touches confirmed orders.
5. **Transition validation** — a terminal order (completed/cancelled/abandoned) cannot be moved to another status (422).

## Files changed
- `settings.py` (agent mode + `agent_replies_enabled` + `draft_expiry_hours`), `api/evolution_webhooks.py` (mode + takeover gating), `services/notifications.py` (new), `api/orders.py` (notify on status change), `db/repositories/orders_repo.py` (terminal-transition guard), `services/order_store.py` (`abandoned` status), `scripts/expire_drafts.py` (new), `tests/test_agent_modes.py` (new). `.env`/`.env.example` (`WHATSAPP_AGENT_MODE`, `DRAFT_EXPIRY_HOURS`).

## Migrations / env
No schema migration (reuses `orders.status`, `order_events`). Env: `WHATSAPP_AGENT_MODE` (default paused), `DRAFT_EXPIRY_HOURS` (default 24). Dev `.env` uses `WHATSAPP_AGENT_MODE=test`.

## Tests & verification
- `pytest` **273 passed** (+5 mode/status tests), ruff clean.
- **Live**: status PATCH → order updated + `status_changed` audit event + `NOTIFICATION_SKIPPED` (correct — non-allowlisted number, no real message); human-takeover → inbound stored, **agent reply suppressed** (count unchanged); draft-expiry job runs safely; mode defaults verified (`paused`).

## Remaining (P0, not in this turn)
- **RBAC / auth (§25):** the dashboard currently has **no authentication** — this is a new subsystem (auth provider, user/role model, route guards, market-scoped access) needing product decisions; must be built before production.
- **Order-number reformat** to `LK-YYYY-######` (§14.6) — currently `LC-TEST-####`.
- **Meta-template notifications** if/when Meta Cloud API is the provider (Evolution free-text works now).
- **Realtime** is 15s polling (spec-approved); Supabase Realtime is an optional upgrade.
- **Full 55-step live staging test** with a physical device + backend-restart mid-flow (§34) — needs an operator with the test phone.

## Production deployment checklist (delta)
- Set `APP_ENV=production`, `ENABLE_DEMO_DATA=false`, `WHATSAPP_AGENT_MODE=paused` → flip to `live` only after staging sign-off + RBAC.
- Configure the production Evolution/Meta number + secrets via env (never hardcoded).
- Schedule `scripts/expire_drafts.py` (cron/Celery beat).
- **Do not go live without RBAC.**
