# WhatsApp Operations Agent - Architecture

## Scope

This document covers the WhatsApp Operations Agent MVP: a single
happy-path flow where a customer requests a laundry pickup via (mock)
WhatsApp, the agent either asks a follow-up question or creates a mock
order + assigns a mock facility + drafts a confirmation, and every
generated reply is queued for human approval before it can be considered
"sent." No classifier agent, no live channels, no risky actions (refunds,
cancellations, discounts, complaint resolution) exist in this build.

## Request flow (end to end)

1. `POST /api/mock-whatsapp/inbound` (channels/mock_whatsapp.py) -
   finds/creates `Customer`, finds/creates an open `Conversation`, stores
   an inbound `Message`. No LLM or agent involvement yet.
2. Admin (or a test/dev script) calls
   `POST /api/admin/conversations/{id}/run-agent`
   (api/routes/admin.py -> agents/whatsapp_operations/agent.py).
3. `OperationsHappyPathAgent.run()` checks `manual_takeover` first - if set,
   it raises immediately and the agent never executes (HTTP 409). Otherwise
   it builds and invokes the LangGraph graph for this conversation.
4. The graph (agents/whatsapp_operations/graph.py) runs these nodes in
   order:
   - `load_conversation_context` - loads conversation/customer, the full
     inbound message history (concatenated as the DB's own record of what
     the customer has said so far), and the market's known facility areas.
   - `assemble_safe_context` - checkpoint node; nothing beyond
     name/area/language is allowed to reach an LLM prompt from here on.
   - `decide_next_action` - deterministic keyword-based slot extraction
     (`tools.extract_order_slots`) over the conversation text decides
     whether `service_type`, `area`, and `pickup_when` are all present. This
     is a placeholder for the future classifier agent, not the classifier
     itself.
   - `execute_tool_loop` - only runs when all three slots are present. Calls
     tools in sequence (get_or_create_customer, add_customer_address,
     get_market_config, calculate_order_total, create_order,
     assign_facility_to_order), capped at `COST_MAX_TOOL_STEPS_PER_RUN`
     steps. Any missing price config, missing facility, or step-cap breach
     forces `decision = "escalate"` rather than guessing.
   - `safety_filter` - a final guard: if the decision is "create_order" but
     the order/facility state is incomplete, force escalation. This is the
     seam where future rules (forbidden commitments, policy checks) plug in.
   - `draft_reply` - builds the actual reply text from
     `agents/whatsapp_operations/prompts.py` templates (deterministic,
     DB/config-sourced values only) and passes it through
     `llm_service.complete()` so the call is still audited like any LLM use,
     even though `MockProvider` just echoes the text back.
   - `create_approval` - wraps the drafted text in a `HumanApproval`
     (`action_type = send_customer_reply` for normal replies,
     `escalate_to_human` when escalating). Nothing is sent yet.
5. Admin calls `POST /api/admin/approvals/{id}/approve` or `/reject`.
   Approving a `send_customer_reply` is the *only* path that calls
   `MockWhatsAppAdapter.send_outbound()` and stores an outbound `Message`
   with `status = mock_sent`. Rejecting just records the decision.
6. Every step above writes an `AIActionLog` row (agent decisions, tool
   calls, LLM calls, approval decisions) - visible via
   `GET /api/admin/ai-action-logs`. `Order` also gets its own `OrderEvent`
   trail independent of the AI log.

## Order state machine

Full target states: `draft, created, awaiting_pickup, picked_up,
processing, ready_for_delivery, out_for_delivery, delivered, cancelled,
escalated` (see `app/models/order.py::ORDER_STATES`).

The agent is only allowed to perform `draft -> created`
(`AGENT_ALLOWED_TRANSITIONS` in the same file);
`services.orders.transition_order()` raises `InvalidOrderTransition` if an
`actor_type="agent"` transition isn't in that set. Every other transition is
manual/admin work for a future task. There is no DB-level trigger enforcing
this yet (Python-level guard only) - see
`docs/checklists/live-whatsapp-readiness.md` for that follow-up.

## Why LangGraph for a "simple" flow

The flow is linear today, but framing it as a graph (rather than a plain
function chain) means the next agent capability (e.g. a real ReAct-style
tool loop, or branching for the future classifier agent) is additive - new
nodes/edges - rather than a rewrite. `graph.py` builds a fresh compiled
graph per run, closing over the request's `AsyncSession`, so every node in
one run shares one DB transaction.

## What this agent cannot do (by construction, not just policy)

There is no tool for refunds, cancellations, discounts, compensation, or
complaint resolution. The tool list in `tools.py` is exhaustive: if it's not
one of the 10 named tools, the agent has no code path to do it.
