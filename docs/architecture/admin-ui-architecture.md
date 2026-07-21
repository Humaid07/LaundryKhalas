# Admin UI Architecture

## Stack

Next.js 14 (App Router), TypeScript, Tailwind CSS, lucide-react icons,
TanStack Query for server state, hand-rolled Tailwind components (no
shadcn/Radix dependency - see "Why no shadcn" below). Lives at
`apps/admin/`, a sibling of the Python backend's `app/` at the repo root.

## Why client-only, no server components touching the API

Every data-fetching page is a `'use client'` component that calls the
FastAPI backend directly from the browser via `lib/api-client.ts`, which
reads `NEXT_PUBLIC_API_BASE_URL`. No Next.js server component, API route,
or server action calls the backend. This is deliberate: it keeps the app
deployable to a static/edge host later (Cloudflare Pages) without needing
a persistent Node server runtime, per the task's Cloudflare-compatibility
direction. `next.config.js` sets `output: "standalone"` for containerized
deploys in the meantime.

## Why no shadcn/Radix

The task allowed "shadcn/ui or clean component equivalents." Given the
small, well-defined component surface needed (badges, cards, a data table,
buttons, empty/loading/error states, a JSON viewer), hand-rolled Tailwind
components in `components/ui/` avoid a large dependency surface (Radix
primitives, shadcn CLI setup) for marginal benefit at this stage. Every
component is small enough to read in one sitting.

## Data flow

1. `lib/api-client.ts` - a single `request()` wrapper around `fetch`.
   Injects `X-Admin-Api-Key` when `admin: true` is passed, builds query
   params, and throws a typed `ApiError` (with `.status` and `.detail`) on
   any non-2xx response or network failure. Every `api.*` method returns a
   typed Promise per `lib/types.ts`.
2. Pages use `useQuery`/`useMutation`/`useQueries` (TanStack Query) against
   `api.*`. Mutations call `queryClient.invalidateQueries` on success so
   the UI reflects backend state immediately - there is no manual reload
   step anywhere in the approve/reject/run-agent/manual-reply/takeover
   flows.
3. Because several backend list endpoints don't embed related data (see
   `docs/audits/admin-ui-start-report.md` §3), some pages compose multiple
   endpoint calls client-side rather than waiting on new backend endpoints
   - e.g. the Conversations inbox uses `useQueries` to fetch each
     conversation's messages (for a latest-message preview) alongside the
     conversation list; the Conversation Detail and Order Detail pages
     derive their "linked order" / "linked conversation" by scanning
     `ai-action-logs` rows for a non-null `order_id`/`conversation_id`
     rather than requiring a new join endpoint.

## Component structure

```
apps/admin/
  app/
    layout.tsx                 QueryClientProvider + globals.css
    page.tsx                    redirects "/" -> "/admin"
    admin/
      layout.tsx                 AdminSidebar + AdminTopbar shell
      page.tsx                    Overview dashboard
      conversations/page.tsx       Conversations inbox
      conversations/[id]/page.tsx    Conversation detail / chat view
      approvals/page.tsx           Approval queue
      orders/page.tsx               Orders list
      orders/[id]/page.tsx           Order detail
      ai-logs/page.tsx              AI action log viewer
      mock-whatsapp/page.tsx         Mock WhatsApp test console
  components/
    layout/   AdminSidebar, AdminTopbar, PageHeader
    ui/       status-badge, card, button, data-table, empty-state,
              loading-state, error-state, json-viewer
    conversations/  ConversationList, ChatMessageBubble (+ AgentDraftBubble),
                     ConversationContextPanel, ManualReplyBox
    approvals/      ApprovalCard
    orders/         OrderTimeline
    logs/           AIActionLogTable
  lib/
    api-client.ts, types.ts, formatters.ts, constants.ts, utils.ts,
    query-client.tsx
```

## Status badges

`components/ui/status-badge.tsx` maps a status string to one of 5 tones
(success/warning/danger/info/neutral) via a single lookup table - the only
place status→color mapping happens, so adding a new backend status value
just means adding one line there.

## Mock-mode safety

`AdminTopbar.tsx` renders a persistent "Mock Environment" badge plus a
Live WhatsApp/Stripe/LLM off-indicator. Every send/approve action button
label explicitly says "mock" ("Approve Mock Reply", "Send Manual Mock
Reply", "Simulate Inbound Message") so no screenshot or demo could be
mistaken for a live system.

## Environment variables

`apps/admin/.env.example`:
- `NEXT_PUBLIC_API_BASE_URL` - browser-facing backend URL (default
  `http://localhost:8000`)
- `NEXT_PUBLIC_ADMIN_API_KEY` - placeholder admin auth, must match the
  backend's `ADMIN_API_KEY`

Both are `NEXT_PUBLIC_*` because they're read by client components -
nothing sensitive is stored here beyond the same placeholder dev key
already used by the backend's own `.env.example`.
