# Presentation Notes — WhatsApp Agent: Humanized + Stateful Orders

**Date:** 2026-07-20 · **Mode:** Mock demo

## 1. What we can show

A WhatsApp-style chat that **feels like a real person is typing** and, crucially,
**turns the conversation into real order data behind the scenes** — bookings,
tracking, cancellations and changes all update a live, queryable order state.

## 2. Suggested demo flow (5 minutes)

1. **Typing feel** — send "Hi". The customer's message appears instantly, then a
   WhatsApp-style *typing…* bubble for ~2–3 seconds, then the reply. It feels
   human, not robotic.
2. **Book a pickup** — click Book Pickup → Dry Cleaning → "2 suits" → "Dubai
   Marina" → "tomorrow evening" → review → **Confirm**. The agent returns a new
   **Order ID (LK-AE-2031)** marked **Active**.
3. **Show the state changed** — open the order API (or dashboard once wired):
   the new order is now in the **active orders** list. *The chat created state,
   not just text.*
4. **Track** — Track Order → "LK-AE-1024" → real status ("pickup scheduled,
   Today 6–8 PM"). Then try a fake ID → it politely says it can't find it
   (never makes one up).
5. **Cancel safely** — Cancel Order → "LK-AE-1024" → it asks to confirm, then
   records a **cancellation request** for the team. It never cancels by itself.
6. **Complete an order** — mark an order completed → it moves from **active** to
   **completed**; metrics update.

## 3. Talking points (plain language)

- "The agent now has a **memory** — it remembers the service, items, area and
  time you gave it earlier in the chat."
- "Every booking becomes a **real order record** the operations team can see —
  that's the foundation the dashboard reads from."
- "It's **honest**: everything says *Demo mode*. It never claims a real order,
  driver, cancellation, or refund happened."
- "It's **safe**: it can't cancel or refund on its own — those go to the team."

## 4. Business value

- The chat is no longer a toy replier — it produces **operational data**.
- Booking, tracking, cancellation and pickup-change requests are captured in a
  structured way, ready to plug into real operations later.
- The humanized typing makes the customer experience feel premium.

## 5. Before vs after

| Before | After |
| --- | --- |
| Instant, robotic replies | 2–3s typing bubble, human feel |
| Order actions were pure text, no state | Bookings/tracking update a real order row |
| No order concept at all | Full mock order lifecycle + dummy orders |
| Nothing for a dashboard to read | Active/completed/metrics endpoints |

## 6. Risks / caveats to mention honestly

- Everything is **mock** — no live WhatsApp, payments, drivers, or facilities.
- Dashboard **UI wiring** to the new order endpoints is the next step (endpoints
  are ready; the admin app already talks to this backend for the chat console).
- Item capture is guided by the buttons; free-typing edge cases are rough.

## 7. What's next

Wire the dashboard's Operations views to the order endpoints, then the
classifier agent.

## Related

- [[2026-07-20-whatsapp-agent-stateful-orders]] · [[mock-order-lifecycle]] ·
  [[whatsapp-agent-memory-and-orders]]
