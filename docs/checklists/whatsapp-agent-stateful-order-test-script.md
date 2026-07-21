# Test Script — WhatsApp Agent Stateful Orders

Manual demo/QA script for the humanized, stateful WhatsApp agent. All mock.

## Setup

```bash
# Backend (:8100)
cd apps/whatsapp-agent
.venv/Scripts/python.exe -m uvicorn main:app --port 8100
# Frontend (:3100)
cd apps/whatsapp-chat && npm run dev
```

Open http://localhost:3100/chat. Banner should read **Mock Mode**.

## A. Humanized typing indicator

1. Send any message (e.g. `Hi`).
2. ✅ Your message appears **immediately**.
3. ✅ A left-aligned **typing bubble** (three animated dots) shows for ~2–3s.
4. ✅ It is **not** a full-screen loader / overlay — the chat stays usable-looking.
5. ✅ Then the agent reply + quick-action buttons appear inside the message.
   - Delay is configurable via `AGENT_MIN_TYPING_DELAY_MS` /
     `AGENT_MAX_TYPING_DELAY_MS` (see `/api/settings/status`).

## B. Book Pickup → creates an ACTIVE order

1. Click **Book Pickup** → agent asks which service (service buttons shown).
2. Click **Dry Cleaning** → agent asks for **item details**.
3. Type `2 suits` → agent asks for **pickup area**.
4. Type `Dubai Marina` → agent asks for **pickup time**.
5. Type `tomorrow evening` → agent shows a **summary** + **Confirm Booking** button.
6. Click **Confirm Booking** → ✅ reply: *"Your mock booking request has been
   created … Order ID: LK-AE-2031 … Status: Active … Demo mode."*
7. ✅ `GET /api/orders/active` includes the new order.

```bash
curl -s http://localhost:8100/api/orders/active | python -m json.tool
```

## C. Track Order (known + unknown)

1. Click **Track Order** → asks for order ID.
2. Type `LK-AE-1024` → ✅ *"Your order LK-AE-1024 is currently pickup scheduled.
   Pickup is set for Today 6 PM – 8 PM. Demo mode — this is mock tracking data."*
3. New chat → **Track Order** → type `LK-9999` → ✅ *"I couldn't find that order
   ID in demo data…"* (never invents a status).

## D. Cancel Order (never auto-cancels)

1. **Cancel Order** → asks for order ID.
2. Type `LK-AE-1024` → ✅ asks to **confirm** sending a cancellation request.
3. Type `yes please` → ✅ *"Your cancellation request has been noted … Demo mode
   — no live cancellation has been made."*
4. ✅ `GET /api/orders/LK-AE-1024` → status `cancellation_requested` (NOT cancelled).
5. Completed order (`LK-AE-1027`) → ✅ *"already completed, so it can't be
   cancelled from the chat."*

## E. Change Pickup Time (records a request)

1. **Change Pickup Time** → asks for order ID + new time.
2. Type `LK-AE-1026, Friday morning` → ✅ *"Noted … pickup time change request …
   (new time: friday morning) … Demo mode."*
3. ✅ `GET /api/orders/LK-AE-1026` → status `pickup_change_requested`,
   `change_request` mentions Friday.

## F. Add More Items (updates the order)

1. In the conversation that booked in **B**, click **Add More Items**.
2. Type `1 winter coat` → ✅ *"I've added this to your request: 1 winter coat …
   Demo mode."*
3. ✅ `GET /api/orders/{that order id}` → `items` now includes the coat.

## G. Mark completed → moves active → completed

```bash
curl -s -X POST http://localhost:8100/api/orders/LK-AE-1024/complete
curl -s http://localhost:8100/api/orders/active     | python -m json.tool  # 1024 gone
curl -s http://localhost:8100/api/orders/completed  | python -m json.tool  # 1024 present
curl -s http://localhost:8100/api/orders/metrics    | python -m json.tool
```

## H. Mock-mode honesty

✅ Every operational reply is demo-tagged. ✅ Never says "your real order is
confirmed", "driver assigned", "cancellation completed", or "refund processed".

## Automated

```bash
cd apps/whatsapp-agent && .venv/Scripts/python.exe -m pytest -q   # 129 passed
```
