# WhatsApp Agent Dashboard Inbox — Architecture

**Location:** `apps/admin`, route `Operations → Customer Facing → WhatsApp Agent`
(`/operations/customer-facing`). Mock/local; no live integrations.

Related: [[whatsapp-agent-architecture]], [[standalone-whatsapp-agent]],
[[whatsapp-cloud-api-integration]], [[privacy-firewall]],
[[internal-dashboard-ui]], [[admin-ui-architecture]].

## Purpose

Give operators a **WhatsApp-Web-style inbox** to view conversations handled by
the WhatsApp Operations Agent and to **take over** only when the agent raises a
flag or the operator chooses to. It is deliberately **not** a test/simulation
console — customer messages are never authored from the dashboard.

## Component tree

```
CustomerFacing
└─ WhatsAppInbox                     (state owner: selection, search, filter,
   │                                  context toggle, mobile view, mutations)
   ├─ WhatsAppChatList               (search, filter chips + counts, chat rows)
   ├─ WhatsAppConversationPane       (header, thread, resolve strip)
   │  ├─ MessageBubble               (customer / agent / human / internal note)
   │  └─ HumanTakeoverComposer       (takeover-gated composer / "Take over")
   └─ ConversationContextPanel       (status, flag card, order card, notes)
      ├─ ConversationFlagCard        (reason, team, suggested reply/action)
      └─ OrderContextCard            (privacy-safe order summary)
```

All components are client components (`"use client"`). State lives entirely in
`WhatsAppInbox`; children are presentational and receive callbacks.

## Data model (`lib/dashboard/whatsapp-inbox.ts`)

Frontend camelCase types that mirror the future API contract:

- `InboxConversation` — id, customerName, phone (masked at render), city, area,
  service, `status`, `priority`, handoffReason, assignedTeam, unread,
  lastMessage/At, `order`, `flag`, notes, `messages[]`.
- `InboxMessage` — id, `sender` (`customer|agent|human|system`), text, createdAt,
  `isInternal`, `authorLabel` ("Sent by Agent"/"Sent by Human"/…), `actions[]`.
- `InboxFlag` — reason, priority, team, suggestedReply?, suggestedAction?.
- `InboxOrder` — id, service, status, area, city, payment, pickupSlot, lastUpdate.

Helpers: `statusMeta` (label + tone), `priorityTone`, `inboxFilters`,
`matchesFilter`, `matchesSearch`, and `seedConversations` (8 seeded threads).

### Status model

`status ∈ { bot, human_needed, human_takeover, resolved }` drives the badge and
the composer state. `priority = urgent` renders a separate **Urgent** badge.
`human_needed` = the agent raised a flag but takeover is **not yet active**; the
operator sees a prominent **Take over**. `human_takeover` = composer open.

## Composer gating (the core rule)

| status           | composer            | control shown                     |
|------------------|---------------------|-----------------------------------|
| `bot`            | hidden              | "Bot is handling…" + Take over    |
| `human_needed`   | hidden              | "Agent flagged this…" + Take over |
| `human_takeover` | **visible**         | Return to bot + reply box         |
| `resolved`       | hidden (disabled)   | "Resolved" + Reopen with takeover |

Human messages are stored with `sender: "human"` and `authorLabel: "Sent by
Human"`. Take over / return to bot / resolve each append an internal system note.

## Mutations → future API mapping

Local state mutations in `WhatsAppInbox` map 1:1 to documented endpoints:

| UI action        | mutation                                   | future endpoint                         |
|------------------|--------------------------------------------|-----------------------------------------|
| Take over        | status→`human_takeover` + note             | `POST /conversations/{id}/human-takeover` |
| Return to bot    | status→`bot`, clear priority/flag + note   | `POST /conversations/{id}/return-to-bot`  |
| Send human reply | append `human` message                     | `POST /conversations/{id}/human-message`  |
| Mark resolved    | status→`resolved` + note                   | `POST /conversations/{id}/resolve`        |
| Load list/thread | `seedConversations`                        | `GET /conversations`, `GET /…/{id}`       |

Swapping the seed for `fetch` behind a flag is the only change needed to go live.

## Responsive layout

`WhatsAppInbox` uses a fixed-height (`h-[38rem]`) CSS grid:

- **xl:** `[300px, 1fr, 300px]` — list + pane + context.
- **md–lg:** `[minmax(260,300)px, 1fr]` — list + pane (context hidden; a header
  toggle controls it on xl).
- **mobile:** single column; `mobileChatOpen` swaps list ↔ pane; a back button in
  the pane header returns to the list.

The pane carries `min-w-0` so the flexible column can shrink (otherwise grid
`min-width:auto` pushes the fixed context column past the container edge).

## Privacy firewall

- Phones **always masked** (`maskPhone`); never rendered in full.
- **Area + city only** — no full address. No payment card/bank data. No secrets,
  API keys, or raw webhook payloads.
- Facility/finance routing appears only as a team label; internal notes/flags are
  visually separated from customer content.

## Determinism

Chat times use `formatClock(iso)` (UTC components) and order "last update" uses
the existing `formatRelativeTime` against `MOCK_NOW` — both deterministic across
SSR and hydration (no React #425). New human-reply timestamps use `Date.now()`
but only after user interaction (post-hydration), so no mismatch.
