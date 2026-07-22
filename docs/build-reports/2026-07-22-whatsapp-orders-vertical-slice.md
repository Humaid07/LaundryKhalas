# Build Report — WhatsApp → Dashboard Orders Vertical Slice

**Date:** 2026-07-22
**Related:** [[2026-07-22-whatsapp-booking-state-machine]] · [[2026-07-22-whatsapp-supabase-order-capture]]

## 1. Problems found (audit)
- Dashboard order/conversation surfaces rendered **mock data as the default** (`lib/dashboard/mock-data.ts`, `whatsapp-inbox.ts`); live data was only an additive overlay gated by `NEXT_PUBLIC_USE_LIVE_WHATSAPP_INBOX`.
- **No Orders nav item**, no order-detail view, no order↔conversation deep link; the interactive inbox selected chats via local state (no URL params).
- Order APIs had **no filters/sort/pagination/needs_attention**, no `/{id}/events`, no `/{id}/conversation`, no `PATCH` status; status changes wrote **no audit event**.
- Order queries **did not exclude `is_demo`**; SQLite auto-seeded demo orders on every startup; no `ENABLE_DEMO_DATA`.
- Backend WhatsApp→DB (booking FSM, idempotency, customer/conversation/message persistence, order_events, human-takeover APIs) was **already solid** and was preserved.

## 2. Files changed
**Backend:** `settings.py` (+`enable_demo_data`), `main.py` (gate seed), `db/repositories/orders_repo.py` (demo exclusion, `list_for_dashboard`, `dashboard_metrics`, `set_status` now writes a `status_changed` event + actor, dashboard fields in `to_read`), `api/orders.py` (`/search`, `/metrics/summary`, `/{id}/events`, `/{id}/conversation`, `PATCH /{id}/status`), `schemas.py` (`OrderPage`, order dashboard fields, `actor_name`).
**Frontend (`apps/admin`):** new `app/(dashboard)/orders/page.tsx`, `components/dashboard/orders/OrdersSection.tsx` (cards + filters + metrics + detail slide-over + status update + polling), `components/dashboard/operations/live/OperationsDeepLink.tsx` (deep-link conversation + order context), `lib/dashboard/order-status.ts`; edits to `lib/dashboard/nav.ts` (Orders nav), `lib/dashboard/whatsapp-agent-api.ts` (new DTOs/methods), `operations/customer-facing/page.tsx` (mount deep link).
**Tests:** `tests/test_orders_dashboard_api.py`.

## 3. Migrations
None new — reuses `orders`/`order_events`/`conversations`/`customers`/`messages` and the booking migrations (000003–000005) already applied. `orders` already carries `is_demo`/`is_test_data`/`source_channel`/`environment`.

## 4. Environment variables
`ENABLE_DEMO_DATA` (default **false** = production-safe; excludes `is_demo` rows + skips SQLite auto-seed). `APP_ENV` (development|staging|production). `.env.example` documents both. Local dev `.env` uses `ENABLE_DEMO_DATA=true`.

## 5. Demo-data guarding
Order list/metrics exclude `is_demo=true` unless `ENABLE_DEMO_DATA=true`. **Real WhatsApp orders are `is_demo=false` → always shown.** SQLite auto-seed now gated. Reference data (services JSON catalogue, pickup_slots, statuses) is untouched — only operational demo rows are guarded. The frontend Orders section is unconditionally backend-backed (no mock fallback).

## 6. APIs created
`GET /api/orders/search?search,status,service_id,pickup_date,source,needs_attention,sort,page,page_size` → `{orders,total,page,page_size}` (each order includes `conversation_id`, masked `customer_phone`, `needs_attention`, `human_takeover`); `GET /api/orders/metrics/summary`; `GET /api/orders/{id}/events`; `GET /api/orders/{id}/conversation`; `PATCH /api/orders/{id}/status` (writes audit event). Existing endpoints preserved.

## 7. Dashboard
New **Orders** section (top-level nav): real metric cards, view tabs (All/New/Active/Needs Attention/Completed/Cancelled), search, status badges, needs-attention highlight, order cards, **detail slide-over** (full order + customer + timeline + status update + "Open Chat in Operations"), **15s polling** + manual refresh. Deep link `/operations/customer-facing?conversationId=…&orderId=…` opens the exact linked conversation (by stored `conversation_id`, never phone/name) with an order-context panel + human-takeover toggle; shareable/refresh-safe; the normal Operations page still works with no params.

## 8. Tests & verification
- `pytest` **268 passed**, ruff clean; admin `tsc` clean for changed files.
- **Live**: `/search` (13 orders, filters, masked phone, conversation_id), `/metrics/summary` (real counts), `/{id}/events` verified against dev/test Supabase.
- **Playwright E2E (headless, 0 console errors):** Orders page renders 8 real cards → click → detail + timeline + Open Chat → navigates to Operations with `conversationId` in URL → deep-link conversation + order-context render.

## 9. Commands
- Backend: `cd apps/whatsapp-agent && .venv/Scripts/python -m uvicorn main:app --reload --port 8101`
- Dashboard: `cd apps/admin && npx next dev -p 3005` (set `NEXT_PUBLIC_WHATSAPP_AGENT_API_URL=http://localhost:8101`)
- Seed reference/demo (explicit only): `python scripts/seed_supabase_test_data.py` (guarded dev/test)
- Tests: `cd apps/whatsapp-agent && .venv/Scripts/python -m pytest -q`

## 10. Known limitations / remaining work
- Draft→abandoned expiry job (§16) not yet scheduled (add a Celery-beat/cron task).
- Deep link opens a dedicated live conversation view; the mock interactive inbox below is not yet fully wired to live send.
- Mobile full-screen order detail + service/pickup-date filter selects are basic; pagination UI is single-page (page_size 60) — infinite-scroll deferred.
- RLS/auth for dashboard mutations relies on the backend service role (no per-user auth yet).
- Row-level realtime deferred in favour of reliable 15s polling (spec-approved).
