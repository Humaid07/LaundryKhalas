# Admin UI Start Report

Performed before building the frontend admin dashboard for the WhatsApp
Operations Agent MVP. Covers current backend API status, the old
prototype's frontend (visual reference only), and the plan for the new UI.

## 1. Existing frontend status

None. This repository (`D:\Laundry Khalas App`) had a Python/FastAPI
backend only (`app/`), no `apps/` or frontend project of any kind. Per the
task instructions, a new `apps/admin/` Next.js project is created rather
than extending anything.

## 2. Backend endpoints available

All confirmed working against the running backend (built and verified in
the prior task, 21/21 backend tests passing, live smoke-tested via curl):

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | liveness |
| POST | `/api/mock-whatsapp/inbound` | simulate inbound WhatsApp message |
| POST | `/api/mock-whatsapp/outbound` | simulate outbound send (low-level; UI uses manual-reply/approve instead) |
| GET | `/api/admin/conversations` | list conversations |
| GET | `/api/admin/conversations/{id}` | conversation + its messages |
| POST | `/api/admin/conversations/{id}/manual-takeover` | set manual takeover |
| POST | `/api/admin/conversations/{id}/release-takeover` | clear manual takeover |
| GET | `/api/admin/conversations/{id}/messages` | message list |
| POST | `/api/admin/conversations/{id}/manual-reply` | admin sends a manual mock reply |
| POST | `/api/admin/conversations/{id}/run-agent` | run the WhatsApp Operations agent |
| GET | `/api/admin/orders` | list orders |
| GET | `/api/admin/orders/{id}` | order detail |
| GET | `/api/admin/approvals` | list approvals (supports `?status=`) |
| GET | `/api/admin/approvals/{id}` | approval detail |
| POST | `/api/admin/approvals/{id}/approve` | approve (sends mock outbound if `send_customer_reply`) |
| POST | `/api/admin/approvals/{id}/reject` | reject |
| GET | `/api/admin/ai-action-logs` | list AI action log rows (supports `?conversation_id=`, `?limit=`) |

All admin routes require header `X-Admin-Api-Key`. Full schemas are in
FastAPI's auto-generated OpenAPI doc at `/docs` and `/openapi.json` - the
frontend's `types.ts` was hand-written to match the actual Pydantic
response models (`app/schemas/*.py`) rather than generated, since the
surface is small and stable.

## 3. Missing endpoints

- **No dashboard/overview aggregate endpoint** (totals for conversations,
  pending approvals, orders, AI actions). The `/admin` overview page
  computes these client-side from the existing list endpoints
  (`GET /api/admin/conversations`, `/approvals`, `/orders`,
  `/ai-action-logs?limit=500`) rather than adding a new backend endpoint,
  per the instruction to avoid adding backend endpoints unless "obviously
  required and safe." This is fine at MVP data volumes; a real `/admin/stats`
  endpoint is a documented future improvement (see
  `docs/checklists/admin-dashboard-mvp.md`, updated below).
- **No pagination** on any list endpoint - the UI requests a reasonably
  large page (e.g. `ai-action-logs?limit=500`) and does client-side
  filtering/search. Fine for MVP data volumes, called out as a limitation.
- **No customer detail/search endpoint** - conversation and order responses
  only expose `customer_id`, not a resolved customer summary (name/phone).
  The UI resolves this by cross-referencing the `customer_id` returned in
  a conversation against... there is in fact no `GET /api/admin/customers`
  endpoint at all. The conversation/order detail views show `customer_id`
  directly since there's no safe way to resolve it to a name/phone without
  a new endpoint. **This is the one gap worth flagging to the backend team**
  - a `GET /api/admin/customers/{id}` (or embedding a masked customer
    summary directly in conversation/order responses) would meaningfully
    improve the UI. Not added in this task per "do not add backend
    endpoints unless obviously required" - documented as a TODO instead.

Three small, safe, additive backend endpoints were added (no model
changes, read-only, no risk to existing behavior):

- `GET /api/admin/orders/{id}/events` - returns the existing `OrderEvent`
  rows for that order (the table and rows already existed; there was
  simply no route reading them). Needed for the Order Detail page's event
  timeline.
- `GET /api/admin/ai-action-logs` now also accepts `?order_id=` (it already
  supported `?conversation_id=`) - a one-line addition so the order detail
  page can show the AI actions tied to that specific order.
- `GET /api/admin/markets` - there was no way to resolve a conversation's
  or order's `market_id` (a UUID) to a readable code like "AE"/"QA"
  anywhere in the existing API surface, and both the Conversations and
  Orders pages need a market column/filter. Returns the existing `Market`
  rows (id, code, name, country, currency, is_active) - no schema/model
  change, just a new read route plus one new Pydantic response schema
  (`app/schemas/market.py`).

Everything else (customer-name resolution, per-conversation/per-order
approval filtering) is handled with existing endpoints and client-side
filtering rather than new backend surface - see the data-volume caveat in
§11.

## 4. Prototype UI observations

Reviewed `D:\LaundryKhalas\LaundryKhalasPrototype` (Next.js 14 App Router,
Tailwind + shadcn/ui, `components.json` style "default"/"slate"). Concretely:

- **Sidebar** (`components/admin/AdminLayout.tsx`): fixed dark (`bg-gray-900`)
  sidebar, grouped nav sections with uppercase micro-labels ("Operations",
  "Agents", "Marketing", ...), lucide-react icons, numeric badges on nav
  items, active-item styling via a **gradient background + colored left
  border** (`linear-gradient(135deg, #c2185b22, #e91e8c22)` with a pink
  `borderLeft`).
- **Status badges** (`components/shared/StatusBadge.tsx`): simple pill,
  `rounded-full px-2.5 py-0.5 text-xs font-semibold`, color driven by a
  lookup map (`STATUS_CLASSES`) keyed by status string.
- **Conversations inbox** (`app/admin/conversations/page.tsx`): status-tab
  filtering, searchable list + thread view, inline "simulate incoming
  message" dev tool.
- **Approvals** (`app/admin/approvals/page.tsx`): urgency-sorted queue,
  action-type tagging.
- Overall: 20 nav items across 6 sections, most pointing at pages that only
  read from a static `lib/mock-data.ts` file (per the earlier prototype
  audit, only one page actually called a real backend).

## 5. Useful ideas from prototype (carried into new UI, as ideas not code)

- Grouped sidebar sections with short section labels.
- Status as a colored pill badge driven by a status→style lookup map.
- Conversation inbox: list + thread, with a way to simulate inbound
  messages without leaving the tool.
- Approval queue as a first-class page, not buried in conversations.
- Inline "quick simulate" affordance - carried forward as the dedicated
  Mock WhatsApp Test Console with quick-fill sample messages.

## 6. UI issues in prototype to improve

- **Gradient + colored-border active nav state** - reads as decorative
  rather than functional; the new sidebar uses a flat, high-contrast
  active state instead (solid tinted background, no gradient), per this
  task's explicit "no random gradients" direction.
- **20 nav items across 6 sections**, most linking to pages backed by
  static mock arrays, not real data - gives a false impression of a
  finished product. The new sidebar only lists the 7 pages that are real
  and backend-wired; nothing links to a page that doesn't work.
- **No visible "mock mode" signal anywhere** - a new team member could
  mistake the demo for a live system. The new UI adds a persistent
  mock-environment indicator in the topbar (explicit requirement below).
- **Numeric nav badges with no visible source** (e.g. a hardcoded `'34'`
  on Orders) - looks live but isn't. New UI badges (e.g. pending-approvals
  count) are computed from real API responses, or omitted if not available
  cheaply.
- Phone numbers shown partially redacted in mock data (`+971 50 XXX 5566`)
  - good instinct, carried forward: the new UI never renders a full raw
    phone number outside of copy actions the admin explicitly needs.

## 7. Proposed new admin UI structure

```
apps/admin/
  app/
    layout.tsx                 root layout, loads globals.css, QueryClientProvider
    admin/
      layout.tsx                admin shell (Sidebar + Topbar)
      page.tsx                  Overview dashboard
      conversations/page.tsx     Conversations inbox
      conversations/[id]/page.tsx  Conversation detail / chat view
      approvals/page.tsx         Approval queue
      orders/page.tsx            Orders list
      orders/[id]/page.tsx        Order detail
      ai-logs/page.tsx           AI action log viewer
      mock-whatsapp/page.tsx      Mock WhatsApp test console
  components/
    layout/  AdminSidebar.tsx, AdminTopbar.tsx, PageHeader.tsx
    ui/      status-badge.tsx, data-table.tsx, empty-state.tsx,
             loading-state.tsx, error-state.tsx, json-viewer.tsx, card.tsx,
             button.tsx
    conversations/  ConversationList.tsx, ChatMessageBubble.tsx,
                     ConversationContextPanel.tsx, ManualReplyBox.tsx
    approvals/      ApprovalCard.tsx
    orders/         OrderTimeline.tsx
    logs/           AIActionLogTable.tsx
  lib/
    api-client.ts, types.ts, formatters.ts, constants.ts, query-client.tsx
```

Every data-fetching page is a client component (`'use client'`) using
TanStack Query against `lib/api-client.ts`, which reads
`NEXT_PUBLIC_API_BASE_URL` (defaults to `http://localhost:8000`) - no
server components touch the FastAPI backend, keeping this deployable to a
static/edge host later (Cloudflare Pages) without a Node server-side
runtime dependency.

## 8. Pages to build now

All 7 requested pages: Overview, Conversations list, Conversation detail,
Approval queue, Orders list, Order detail, AI action logs, plus the Mock
WhatsApp Test Console (8 routes total including `/admin` itself).

## 9. Pages to defer

- Classifier/intent management UI - classifier agent doesn't exist yet.
- SEO/marketing UI - out of scope entirely.
- Driver dispatch / customer-facing app UI - out of scope entirely.
- Customer detail/search page - blocked on the missing customer-summary
  endpoint noted in §3.
- Market/facility/pricing config management UI - backend has no CRUD
  endpoints for these yet (seed-data only).

## 10. API integration plan

- `lib/api-client.ts` wraps `fetch`, injects `X-Admin-Api-Key` from
  `NEXT_PUBLIC_ADMIN_API_KEY` (defaults to the same dev placeholder key
  used in `.env.example`), throws a typed `ApiError` on non-2xx so
  TanStack Query's error state renders consistently everywhere.
- `lib/types.ts` mirrors the backend Pydantic schemas by hand (small
  surface, no codegen needed).
- Every list page uses `useQuery` with a short `staleTime` and manual
  refresh button; every mutation (`run-agent`, `approve`, `reject`,
  `manual-takeover`, `manual-reply`, `mock-whatsapp/inbound`) uses
  `useMutation` + `invalidateQueries` so the UI reflects backend state
  immediately without a manual reload.

## 11. Risks / blockers

- No customer name/phone resolution endpoint (§3) - mitigated by showing
  `customer_id` and whatever the conversation/order response already
  includes; not a blocker, just a known gap.
- No pagination - mitigated with a high `limit` on `ai-action-logs` and
  client-side search/filter for the others; fine at current data volumes,
  flagged as future work.
- CORS: the FastAPI backend does not currently set an explicit CORS
  policy for a browser origin other than same-origin. Since the admin UI
  runs on `http://localhost:3000` and the API on `http://localhost:8000`,
  this is a cross-origin browser request. **Resolved as part of this task**
  by adding a narrow, explicit CORS allow-list to `app/main.py` (only
  `http://localhost:3000` and `http://127.0.0.1:3000` in this dev config,
  not a wildcard) - the smallest safe backend change required for the UI
  to function at all, consistent with "only add minimal backend endpoint
  [or change] if it is obviously required and safe."
