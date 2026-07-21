"""Laundry Class WhatsApp agent — LangChain + LangGraph implementation.

A self-contained conversational agent for the file-based testing phase:

* File-based knowledge base (knowledge_base/laundry_class_knowledge_base.md +
  dummy_orders.json) as the single source of truth — no invented prices/policies.
* LangGraph state machine with a persistent SQLite checkpointer for short-term
  conversation memory, keyed by thread_id = "whatsapp:<phone>" so each WhatsApp
  number has isolated memory that survives an application restart.
* Intent routing, slot-based order collection, dummy-order lookup, and a
  deterministic human-handoff workflow with a structured admin notification.
* Mock-first: the "LLM" node is a deterministic LangChain BaseChatModel by
  default (no live calls, zero cost); a real provider is swappable via env but
  off unless explicitly enabled.
"""
