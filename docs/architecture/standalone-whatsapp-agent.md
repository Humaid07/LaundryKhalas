# Standalone WhatsApp Agent — Architecture

## What "standalone" means here

This is a second, independent codebase from the main system (`app/` +
`apps/admin/`). It does not share a database, models, or API with the main
backend. It exists to answer one question in isolation: *can a single,
focused agent hold a WhatsApp-style laundry/cleaning conversation, refuse
everything else, and never invent facts?* — without the surrounding weight
of the full order-management system, approval queue, or admin dashboard.

Per the task that created it, the main system's admin dashboard, classifier
agent, and full order flow are explicitly out of scope here and untouched.

## Directory layout

```
apps/whatsapp-agent/        Backend (FastAPI, Python 3.11+)
  main.py                    App wiring: CORS, routers, /health, DB init
  settings.py                Env-driven config; the only place "mock vs
                              live" is decided (live_llm_ready /
                              live_whatsapp_ready)
  db.py, models.py           SQLAlchemy async, SQLite by default
                              (Conversation, Message, AgentLog)
  schemas.py                 Pydantic request/response models
  services/
    domain_guard.py           Layer 1 domain filter (keyword/pattern)
    storage.py                Shared conversation/message/log persistence
  channels/
    whatsapp_base.py           WhatsAppChannel interface
    mock_whatsapp.py           Zero-network mock channel (default)
    meta_whatsapp.py           Real Meta Cloud API channel (opt-in only)
  llm/
    service.py                 Single LLM entry point - provider selection
    providers/
      base.py, mock.py, anthropic.py, openai.py
  agents/whatsapp_agent/
    agent.py                   Orchestration: guard -> intent -> LLM
    prompts.py                 System prompt + knowledge-base loader
    tools.py                   Deterministic slot/intent extraction
  config/
    laundrykhalas_knowledge.json   Editable brand/service/pricing facts
  api/
    chat.py, webhooks.py, settings_route.py
  tests/                      pytest suite (28 tests)

apps/whatsapp-chat/         Frontend (Next.js 14, TypeScript, Tailwind)
  app/chat/page.tsx           WhatsApp-Web-style chat console
  app/settings/page.tsx       Read-only mode/status page
  components/                 Sidebar, ChatHeader, MessageBubble, Composer,
                               DebugPanel, ModeBanner, etc.
  lib/                        api-client.ts, types.ts, formatters.ts,
                               local-conversations.ts (client-only
                               conversation list, see below)
```

## Why two new top-level `apps/` entries, not folders inside `app/`

The task's file paths (`services/`, `channels/`, `llm/`, `agents/`,
`config/` with no `app/` prefix) describe a self-contained project, and the
task explicitly says not to rebuild the main order-management database.
Nesting this inside the existing `app/` package would have meant either
sharing its Postgres schema (explicitly ruled out) or maintaining two
unrelated model sets in one package, which is more confusing than two
clearly-separated `apps/` entries. `apps/admin/` already established the
convention of `apps/<name>/` for a standalone deployable; this follows it
for both the new backend and its frontend.

## Ports

The main system's admin frontend already owns port 3000
(`apps/admin/`, `docker-compose.yml`). This standalone agent's backend
runs on **8100** (vs. the main API's 8000) and its chat UI runs on
**3100** (vs. admin's 3000), so all four can run side by side without a
port clash. `ALLOWED_ORIGINS` in `apps/whatsapp-agent/.env.example`
defaults to `http://localhost:3100`, not the `3000` mentioned in the
original task brief - the 3000 value would have broken CORS out of the
box against admin's already-claimed port. See `docs/build-reports/
2026-07-18-standalone-whatsapp-agent.md` §16 for the full note.

## Data model

Deliberately minimal - three tables, no relation to the main system's
`Order`/`HumanApproval`/`Facility` schema:

- **Conversation** - id, channel (`local` | `whatsapp`), customer_phone,
  customer_name, status, timestamps.
- **Message** - id, conversation_id, direction (inbound/outbound),
  sender_type, text, domain_status, raw_payload_json (stores the original
  Meta webhook message object when the channel is `whatsapp`).
- **AgentLog** - id, conversation_id, message_id, action, input_json,
  output_json, provider, model, success, error_message. One row per
  agent turn (`agent_reply` for local test chat, `whatsapp_reply` for
  webhook-driven turns) - not per-tool-call like the main system's
  `AIActionLog`, since this agent has no tools beyond the deterministic
  helpers in `tools.py`.

SQLite (`sqlite+aiosqlite:///./whatsapp_agent.db`) by default per the task
brief ("SQLite allowed only for local standalone MVP"); `DATABASE_URL` can
point at a Postgres instance instead with no model changes, since both use
the same SQLAlchemy async models.

## Request flow

**Local test chat** (`POST /api/test-chat/message`): store inbound message
→ `agents.whatsapp_agent.agent.handle_message()` → store outbound reply +
`AgentLog` row → return `{agent_reply, domain, mode, provider}` to the UI.

**WhatsApp webhook** (`POST /webhooks/whatsapp`): verify `X-Hub-Signature-
256` if `META_WHATSAPP_APP_SECRET` is set → parse Meta's payload shape →
same `handle_message()` call per extracted message → send via
`MetaWhatsAppChannel` if `settings.live_whatsapp_ready`, else
`MockWhatsAppChannel` → store + log either way.

Both paths go through the exact same agent function, so local-mode testing
genuinely exercises the same logic a live webhook would use - the only
difference is which channel adapter delivers the reply.

## Client-side conversation list (frontend)

The backend intentionally has no `GET /conversations` list endpoint (out of
the task's required endpoint list). The chat UI's sidebar is populated from
a small `localStorage`-backed list (`lib/local-conversations.ts`) updated
after each send - a real per-browser convenience, not backend state. This
keeps the backend surface exactly as specified while still giving the chat
UI a WhatsApp-Web-like conversation list. If a real multi-admin console is
needed later, that's a small addition to `api/chat.py`, not a redesign.

## Interactive message actions, service catalog, and quick actions

First built as a fixed toolbar/dropdown above the composer, then
explicitly corrected to attach buttons to the specific agent message
asking a question instead - matching how real WhatsApp interactive
messages actually work. See `docs/build-reports/
2026-07-18-whatsapp-interactive-message-actions.md` for the full
before/after and the two bugs found fixing it.

- **`agents/whatsapp_agent/actions.py`** is the single source of truth for
  every interactive button: `Action(id, label, type)`, `MAIN_MENU_ACTIONS`
  (6 quick actions), `SERVICE_ACTIONS` (7 service options, kept in sync
  with `config/laundrykhalas_knowledge.json`'s `service_catalog`), and
  `resolve_intent_override(action_id)`. There is no longer a
  frontend-side copy of this catalog (the old `lib/constants.ts` was
  deleted) - the frontend renders whatever `actions` array the backend
  sends, nothing more.
- **`actions: list[Action]`** on `AgentReply` / `TestChatResponse` -
  computed server-side in `agent.py`, independent of whichever provider
  (mock or a real LLM) generated the reply *text*. Populated with
  `MAIN_MENU_ACTIONS` on the welcome message and the out-of-domain
  refusal, `SERVICE_ACTIONS` when the agent's reply is asking for the
  service slot specifically, empty otherwise.
- **`action_id`** on `TestChatRequest` (optional) - when a customer clicks
  a button, the frontend sends `{message: label, action_id: "book_pickup"}`
  ; `resolve_intent_override()` maps the id straight to an intent,
  bypassing keyword guessing entirely (more reliable than re-parsing the
  button's own label text, though the label text alone also resolves
  correctly for every button as a free-text fallback).
- **`components/MessageBubble.tsx`** renders `message.actions` as a
  stacked column of bordered buttons attached directly below the agent's
  bubble - not a separate global component. Actions are **not persisted**
  to the database (no new column on `Message`) - only the just-returned
  live response carries them, so a reloaded conversation's older bubbles
  lose their buttons (documented limitation, not a bug - all flows still
  work via free text).
- **Welcome-menu gating.** A vague opener ("Hi", "I need laundry", "I
  need help", "What services do you offer?") gets the fixed welcome text
  ("Hi 👋 Welcome to LaundryKhalas. How can we help you today?") with
  `MAIN_MENU_ACTIONS` attached, rather than jumping straight into slot
  collection. `agent.py`'s `_BOOKING_ENTRY_INTENTS` set plus a
  `booking_in_progress` check (true once any slot is already known from
  earlier in the conversation) decide whether a message enters the
  booking flow or falls back to the welcome menu - so an ambiguous reply
  *mid*-booking doesn't derail the flow, but a genuinely fresh unclear
  message does get the menu.
- **Order-flow intents without an Order model.** `track_order_request`,
  `cancel_order_request`, `change_pickup_time_request`,
  `add_items_request`, `call_support_request` remain `detect_intent()`
  values (or `resolve_intent_override()` results, from a button click).
  There is deliberately no `Order` table anywhere in this standalone
  codebase (see the data-model section above) - these flows ask for an
  Order ID and echo it back, never look one up or claim to act on it;
  every reply is explicitly demo-labeled, per the task's requirement not
  to pretend a real order was tracked, cancelled, or changed.
- **Multi-turn order-flow state without a new DB column.**
  `tools.pending_order_action(history)` inspects the *previous* agent
  message for a marker substring unique to each ask - so a bare follow-up
  like "LK-1023" resolves correctly on the next turn without persisting
  any extra state. **This marker-string coupling is fragile** - it broke
  twice already when the reply wording changed without updating the
  matching marker (see the build report's bug logs). Any future wording
  change to an order-flow ask must also update
  `tools._PENDING_ACTION_MARKERS`, or add a test that would catch the
  drift (the existing multi-turn tests in `test_quick_actions.py` do,
  but only for the exact scenarios they cover).

## Relationship to the main system

No code is shared. Two independent Meta WhatsApp Cloud API integration
points now exist in this repository - this one (working payload-shape code,
never live-tested) and the main system's `app/channels/meta_whatsapp_stub.py`
(a stub that raises `NotImplementedError`). See
`docs/checklists/live-whatsapp-readiness.md` for the explicit flag that a
decision is needed on which one (if either) becomes the real production
integration before either is pointed at a real phone number.
