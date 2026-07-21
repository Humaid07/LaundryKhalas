# Build Report — WhatsApp Agent Inbox UI

**Date:** 2026-07-21
**Area:** `apps/admin` → Operations → Customer Facing → WhatsApp Agent

## 1. Task objective

Replace the WhatsApp Agent **test console** in the dashboard with a real,
operational **WhatsApp-style inbox**: a chat list on the left, the selected
conversation on the right, human takeover only when the agent raises a flag (or
the operator opts in), and a message composer only during human takeover. Remove
all "send test message / simulate customer" controls — real customer messages
come from a device / WhatsApp Cloud API webhook (or a seed), never from the
dashboard.

## 2. What was built

A full WhatsApp-Web-style inbox rendered as the flagship, full-width surface at
the top of **Customer Facing**:

- **Left chat list** — search, filter chips (All / Human Needed / Urgent /
  Active Orders / Resolved) with live counts, and one row per conversation
  (avatar, name, masked-phone-free preview, timestamp, unread badge, status
  badge, urgent indicator, order id).
- **Right conversation pane** — header (name, masked phone, area/city, service,
  urgent + status badges, linked order id), a WhatsApp-style message thread
  (customer bubbles left, agent/human bubbles right, internal notes as separate
  cards), a "Mark resolved" strip, and the takeover-gated composer.
- **Context panel (xl+)** — conversation status/priority, the handoff/flag card
  (reason, team, suggested reply/action), a compact privacy-safe linked-order
  summary, and internal notes. Toggleable from the pane header.
- **Human takeover** — when a flag is raised the pane shows *"The agent flagged
  this for a human. Take over to reply."* with a prominent **Take over**; when no
  flag, *"Bot is handling this conversation."* The composer is hidden until
  takeover is active, then shows **Return to bot** + a real reply box; resolved
  conversations disable the composer.

## 3. Why it was built

The previous console behaved like a developer tool — it let operators type
customer messages and fire preset "test" prompts, which does not match how a real
WhatsApp inbox works and is not demo-appropriate. The inbox reframes the surface
around the real operator job: **view** conversations, **read** flags, **take
over** when needed, **reply** manually, and see **order context** — without ever
simulating customers.

## 4. Files created

- `apps/admin/lib/dashboard/whatsapp-inbox.ts` — inbox data model
  (`InboxConversation`, `InboxMessage`, `InboxFlag`, `InboxOrder`), status/priority
  tone maps, filter chips + `matchesFilter`/`matchesSearch`, and **8 seeded
  conversations** (the 6 spec scenarios + 2 extra for filter coverage).
- `apps/admin/components/dashboard/whatsapp/WhatsAppInbox.tsx` — top-level
  layout + all state (selection, search, filter, context toggle, mobile view) and
  the mutations (take over, return to bot, resolve, human reply).
- `apps/admin/components/dashboard/whatsapp/WhatsAppChatList.tsx` — left panel.
- `apps/admin/components/dashboard/whatsapp/WhatsAppConversationPane.tsx` — right
  pane, message bubbles, and the exported `ConversationContextPanel`.
- `apps/admin/components/dashboard/whatsapp/HumanTakeoverComposer.tsx` — the
  takeover-gated composer / "Take over" control.
- `apps/admin/components/dashboard/whatsapp/ConversationFlagCard.tsx` — handoff
  flag card + `OrderContextCard`.

## 5. Files modified

- `apps/admin/components/dashboard/operations/CustomerFacing.tsx` — renders
  `<WhatsAppInbox />` full-width above the support tabs; removed the "WhatsApp
  Agent" tab (and its `MessageCircle` import) from the tab strip.
- `apps/admin/lib/dashboard/formatters.ts` — added `formatClock(iso)`
  (deterministic UTC-based chat time, no hydration drift).
- `apps/admin/app/(dashboard)/operations/customer-facing/page.tsx` — updated the
  page description (console → inbox wording).

## 6. Files removed

- `apps/admin/components/dashboard/WhatsAppAgentConsole.tsx` — the old test
  console (test message box, preset "customer" messages, backend-wired send).

`apps/admin/lib/dashboard/whatsapp-agent-api.ts` was left in place (now unused,
not imported) as the future live-backend client; it is not referenced by the
inbox.

## 7. API endpoints

None added or called. The inbox is **frontend-seeded mock** for now. The data
model and the four mutations map 1:1 to the documented future contract so real
conversations can populate the same structures without UI change:

```
GET  /api/conversations
GET  /api/conversations/{id}
POST /api/conversations/{id}/human-takeover
POST /api/conversations/{id}/return-to-bot
POST /api/conversations/{id}/human-message
POST /api/conversations/{id}/resolve
```

## 8. Database

No database changes. Seed data lives in `whatsapp-inbox.ts`.

## 9. UI pages/components

See §4/§5. Net effect on Customer Facing: the WhatsApp Agent is now a full-width
inbox at the top; the Conversations / Tickets / Cancellations / Order Changes /
Follow-ups tabs and the right sidebar are unchanged.

## 10. Agent behavior

No change to the backend agent. The inbox *displays* agent messages, flags, and
suggested replies, and lets a human take over — the MVP human-in-the-loop model.

## 11. What is mock-only

Everything in this build: the 8 conversations are seeded; take over / return to
bot / resolve / human reply mutate local React state only. No live WhatsApp,
LLM, or Stripe. Consistent with the "no live integrations without approval" rule.

## 12. What is intentionally deferred

- Wiring to real `/api/conversations*` endpoints + a webhook that seeds inbound
  messages into the same shape.
- Persisting takeover/resolve/reply server-side (currently in-memory, resets on
  reload).
- A local/mock webhook *simulator* (kept **out** of the operator dashboard by
  design — it belongs in Dev & Automation or a separate tool).
- Surfacing backend connection/health details in **Dev & Automation** (removed
  from the inbox per the "no technical panels in the operator view" rule).

## 13. Tests run

- `tsc --noEmit` on the new/changed files — **0 errors in this build's files.**
  (Note: the repo has **87 pre-existing** `tsc` errors in the shared filter
  engine `lib/dashboard/filters.ts` + 5 unrelated section components, caused by an
  index signature added to `Filterable`. They predate and are unrelated to this
  task; the inbox does not use that engine. Not fixed here to avoid an unrelated
  refactor.)
- Playwright end-to-end against the dev server (light, dark, 390px mobile).

## 14. Test results

30 UI assertions pass (2 initial "failures" were false negatives — the name also
appears in the separate Conversations table below the inbox; confirmed correct by
scoping the assertion to the chat list). Verified:

- Inbox renders; chat list shows seeded customers; **no** test-message box, **no**
  preset messages, **no** "Live Agent Console".
- Status badges (Bot Handling / Human Needed / Urgent) present.
- Refund chat shows flag reason, suggested reply, team routing, linked order.
- **Take over** hidden-composer → visible-composer transition; human reply is
  stored as a "Sent by Human" bubble; **Return to bot** hides the composer;
  resolved chat has no active composer.
- Urgent filter and "hotel" search correctly scope the chat list.
- Dark mode correct; **0 horizontal overflow** on mobile; back button appears
  after opening a chat; **0 console/page errors**.

## 15. Bugs/issues found & fixed

- Context panel clipped at the viewport edge because grid items default to
  `min-width:auto`. Fixed by adding `min-w-0` to the conversation pane so the
  flexible column can shrink and the fixed context column fits.

## 16. Known limitations

- Mock/local only; state resets on reload (no persistence).
- Order context is self-contained mock data (not joined to the `orders` dataset).
- The separate legacy "Conversations" table still exists below the inbox (a
  compact ops overview) — intentionally kept; it partially overlaps the inbox.

## 17. Security / privacy notes

- Phones are **always masked** at render (`maskPhone`); no full phone appears.
- No full address — **area + city only**; no card/bank details; no API keys, no
  raw webhook payloads, no secrets.
- Internal notes/flags render as clearly-separated internal cards, never as
  customer-facing content.

## 18. Cost / LLM usage

None. No LLM or external calls in this build.

## 19. Screens to demo

Customer Facing → WhatsApp Agent: (1) inbox overview, (2) urgent refund chat with
flag card + suggested reply, (3) take over → send human reply, (4) return to bot,
(5) dark mode, (6) mobile list → chat with back button.

## 20. Commands to run

```
cd apps/admin
npm run dev            # http://localhost:3005 (or another port)
# open /operations/customer-facing
```

## 21. Next recommended step

Stand up the mock `/api/conversations*` endpoints in `apps/whatsapp-agent`, point
`whatsapp-inbox.ts` at them behind a flag, and seed inbound messages from a
webhook so the same UI shows real conversations.
