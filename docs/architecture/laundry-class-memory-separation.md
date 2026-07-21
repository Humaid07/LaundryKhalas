# How Laundry Class memory is separated by WhatsApp number

Short note for the deliverable: how one customer's conversation memory is kept
completely separate from another's.

## The mechanism: one thread per phone number

Every WhatsApp number maps to a **stable thread id**:

```
thread_id = "whatsapp:<phone_number>"     e.g. whatsapp:+971500000101
```

(`laundry_class/runtime.py → thread_id_for()`.)

The LangGraph agent runs with a **checkpointer** (short-term memory store). On
every message we invoke the graph with `config={"configurable": {"thread_id": tid}}`.
LangGraph uses that `thread_id` as the key under which it loads the prior
conversation state and saves the new state:

- **Same phone → same thread_id → same memory.** The customer's earlier messages,
  collected order slots, current order id, and handoff status are loaded back on
  every turn, so the agent remembers and does not restart.
- **Different phone → different thread_id → a completely separate memory slice.**
  There is no shared key, so number B's graph run never loads number A's state.

## Why one customer can never see another's data

1. **Physical isolation:** the checkpointer only ever loads the state stored under
   the current message's `thread_id`. Number B's run simply has no access path to
   number A's checkpoint.
2. **No global state:** the agent keeps nothing about a conversation in module-level
   variables — everything lives in the per-thread state.
3. **Explicit privacy guard:** even if a customer *asks* about someone else by name
   ("What is Daniel's order?"), a global guard (`graph.py → _dispatch`) refuses:
   "I can't share another customer's information." Recall questions ("what address
   did I give you?") are answered **only** from the current thread's own memory.

This is verified by **Test Case 8**: phone A stores a name + address + order; phone B
receives none of it and is refused Daniel's order; returning to phone A still recalls
its own details. The two runs log **different thread_ids**.

## Persistence

For testing we use a persistent `AsyncSqliteSaver` checkpointer
(`laundry_class_memory.sqlite`). Because state is keyed by `thread_id` in that file,
memory both **survives an application restart** (Test Part 8) and **stays isolated**
per number across restarts. An in-memory checkpointer is available for the first
functional test but is replaced by the persistent one for the final implementation.

## What is (and is not) stored

Stored per thread: running messages, phone number, name, order slots (service, items,
area, pickup time, payment method, address), current order id, and handoff status.
**Not stored:** passwords, card numbers, CVV, PIN, OTPs, or tokens. Phone numbers are
masked in application logs; only the team-facing handoff channel keeps the full number
because it is operationally required to act on the case.
