# Presentation Notes — Laundry Class WhatsApp Agent (KB + memory + handoff)

**Date:** 2026-07-21 · **Mode:** MOCK · Live WhatsApp/LLM/Stripe: Off

## 1. What we can show in the demo
A WhatsApp-style assistant that answers real Laundry Class prices from a file knowledge
base, collects an order across several messages while **remembering** everything, escalates
refunds/damage/human requests to a person, keeps each phone number's memory **private and
separate**, and **survives an app restart** without forgetting the conversation.

## 2. Suggested demo flow (terminal console)
`python scripts/lc_chat.py --phone +971500000101`
1. "how much is dry cleaning for a suit?" → AED 45. "and a shirt?" → AED 9 (remembers we're on dry cleaning, no repeated greeting).
2. "what's the total for one suit and three shirts?" → AED 72 estimate, free delivery.
3. New number: place an order over several messages (name, service, items, area, time, payment) → order summary → confirm → dummy reference `LC-TEST-9xxx`. Then "what time did I choose?" → recalled.
4. Ahmed's number (+971500000101): "where is my order?" → LC-TEST-1001 Processing; "what did I send?"; "how much do I pay?".
5. "my silk dress came back torn" → apology + **handoff**; show `logs/admin_handoffs.log`.
6. Restart the console, ask "what pickup time did I request?" → still remembered.
7. Two numbers side by side → number B cannot see number A's address/order.

## 3. Screenshots needed
- The suit→shirt→total price exchange.
- The order collection + confirmation with the dummy reference.
- The damage complaint reply + the structured admin notification in `logs/admin_handoffs.log`.
- The restart recall.
- The two-number isolation (B refused A's data).

## 4. Talking points
- **Grounded, never invents:** every price comes from the knowledge-base file; unlisted
  items (e.g. a saddle) get "the team needs to inspect it," never a made-up number.
- **Real memory:** LangGraph checkpointer per WhatsApp number; remembers across turns and
  across restarts; one customer can never see another's data.
- **Safe by design:** refunds/damage/payment disputes/human requests go to a person; the
  agent never approves a refund, promises compensation, admits fault, or confirms a new
  delivery time on its own.
- **Mock-first:** zero LLM/WhatsApp/Stripe calls, zero cost; a real LLM is a config flip away.

## 5. Technical explanation in simple language
Each phone number gets its own private "notebook" (thread). Every message updates the
notebook and is saved to disk, so the assistant remembers even after a restart, and never
mixes up two customers. Answers are looked up in a knowledge-base file, so it can't make up
prices. Anything risky is handed to a human with a tidy summary.

## 6. Business value
A WhatsApp assistant that handles the safe, high-volume questions (prices, pickups, order
status) accurately and hands the tricky ones (refunds, damage) to staff with full context —
faster replies, fewer mistakes, and a clear audit trail, all before spending a cent on live AI.

## 7. Before vs after
- **Before:** rules-based agent, no persistent per-customer memory, no file knowledge base.
- **After:** LangGraph memory per number that survives restarts, a file knowledge base with
  real prices, and a structured human-handoff workflow.

## 8. Risks / caveats to mention honestly
- Deterministic mock model has an accuracy ceiling on free-form phrasing; a real LLM node is
  wired and off by default.
- One known gap (TC9): if a customer re-describes items already stated, the estimate
  over-counts — still labelled an estimate, never an invented price; fixed by the live node.
- Not yet wired to a live WhatsApp number or the admin dashboard UI (library + CLI for now).

## 9. What is coming next
Wire the agent behind the existing chat API / a WhatsApp webhook and surface the handoff
queue in the admin dashboard; optionally enable the live LLM node in staging.
