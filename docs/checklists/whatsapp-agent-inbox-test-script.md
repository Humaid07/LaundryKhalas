# WhatsApp Agent Inbox — Manual Test Script

Route: `/operations/customer-facing` → **WhatsApp Agent** (top, full-width).
Mock/local; nothing here sends live messages.

## Setup

```
cd apps/admin
npm run dev            # http://localhost:3005 (or another free port)
```

Open `/operations/customer-facing`.

## Chat list (left)

- [ ] A WhatsApp-style chat list is visible with search + filter chips.
- [ ] Filter chips show live counts: All 8 · Human Needed 4 · Urgent 1 ·
      Active Orders 5 · Resolved 1.
- [ ] Each row shows avatar, name, last-message preview, time, and a status badge
      (Bot Handling / Human Needed / Human Takeover / Resolved); urgent rows show
      an **Urgent** badge; rows with an order show the order id.
- [ ] Search "hotel" → only the B2B lead (Jumeirah Bay Hotel) remains.
- [ ] Filter **Urgent** → only Amaan Patel (refund) remains.
- [ ] Filter **Resolved** → only Mariam Zayed remains.
- [ ] Clearing search + selecting **All** restores every row.

## Conversation pane (right)

- [ ] Selecting a chat opens the thread on the right.
- [ ] Header shows name, **masked** phone, area/city, service, status/urgent
      badges, and the linked order id.
- [ ] Customer messages are left-aligned; agent/human messages right-aligned.
- [ ] Agent bubbles show "Sent by Agent"; internal flags render as a **separate
      note pill**, not a chat bubble.

## Flag / handoff

- [ ] Open **Amaan Patel** (refund). Context panel shows: Human intervention
      required, **Urgent**, Reason = Refund request, Team = Customer Facing /
      Finance, and the suggested reply.
- [ ] Open **Hassan Ali** (damaged item): High priority, suggested action asks for
      order id + photo.
- [ ] Open **Jumeirah Bay Hotel** (B2B): Medium, team = Sales / Partner
      Acquisition.
- [ ] Open **Sara Juma** (payment): High, team = Customer Facing / Finance.

## Human takeover

- [ ] On a flagged chat, the composer is **hidden**; the pane shows "The agent
      flagged this for a human." + **Take over**.
- [ ] On a plain bot chat (e.g. Aisha Rahman), it shows "Bot is handling this
      conversation." + Take over; composer hidden.
- [ ] Click **Take over** → composer appears, "Human takeover active" note is
      added, **Return to bot** appears.
- [ ] Type a reply and send → it appears right-aligned as **Sent by Human**.
- [ ] (Optional) Click "Use suggested…" to prefill the reply box.
- [ ] Click **Return to bot** → composer hides, "Bot is handling…" returns.
- [ ] Click **Mark resolved** → status becomes Resolved and the composer is
      disabled ("Reopen with takeover" available).

## Order context

- [ ] Chats with an order show a compact card: order id, service, status,
      area/city, payment, pickup slot, last update.
- [ ] **No full address, no full phone, no card details** anywhere.
- [ ] A chat with no order (e.g. Aisha) shows "No linked order yet".

## Removed / must NOT be present

- [ ] No "Send inbound message" box.
- [ ] No preset test messages (e.g. "What's the weather today?").
- [ ] No "Live Agent Console" / backend URL / technical status panel in the inbox.
- [ ] No way to type a **customer** message from the dashboard.

## Responsive / theme

- [ ] xl: list + pane + context panel; the pane header toggle hides/shows context.
- [ ] Mobile (≤767px): list first; tapping a chat opens the thread; a **back**
      button returns to the list; composer only during takeover.
- [ ] No horizontal page scroll on mobile.
- [ ] Dark mode: surfaces, bubbles, and badges all read correctly.
- [ ] No console errors in any of the above.
