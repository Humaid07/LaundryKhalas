# Build Report: WhatsApp Interactive Message Actions

## 1. Build title

Move quick actions from a permanent toolbar into WhatsApp-style interactive
buttons attached to agent messages, standalone WhatsApp Agent.

## 2. Date

2026-07-18

## 3. Task objective

Correct a design mistake in the previous iteration: the 6 quick actions
(Book Pickup, Track Order, Change Pickup Time, Add More Items, Cancel
Order, Call Support) and the service-selection options were rendered as a
**permanent toolbar and dropdown** above the message composer - always
visible, disconnected from the conversation. Per explicit instruction,
this is wrong: real WhatsApp interactive messages attach their buttons to
the specific message that's asking a question, not to a global footer.
This build removes the toolbar/dropdown entirely and moves both action
sets into the agent's own message bubbles.

## 4. Why quick actions were moved into agent messages

A fixed toolbar implies every action is always valid regardless of
conversation state (e.g. "Track Order" sitting there even mid-way through
answering a pricing question) and doesn't match how WhatsApp's own
interactive/quick-reply messages work - buttons are a property of the
specific message that offered them, shown once, tied to that question.
Attaching actions to the message instead makes the UI honestly reflect
"here is what you can do *right now*, in response to *this*", which is
also why the buttons disappear once their question is answered (e.g. the
7 service buttons vanish the instant a service is chosen).

## 5. How interactive message actions work

**Backend** (`agents/whatsapp_agent/actions.py`, new file):

- `Action` (id, label, type="quick_reply") - a plain dataclass, not a DB
  model; actions are a UI hint computed fresh per turn, never persisted.
- `MAIN_MENU_ACTIONS` - the 6 quick actions.
- `SERVICE_ACTIONS` - the 7 service options (same catalog as before).
- `resolve_intent_override(action_id)` - when a customer clicks a button,
  the frontend sends its `action_id` back; this maps it directly to an
  intent (`book_pickup` → `new_pickup_request`, a service id → also
  `new_pickup_request`, etc.), bypassing keyword guessing entirely. This
  is strictly more reliable than re-parsing the button's own label text.

`agents/whatsapp_agent/agent.py`'s `AgentReply` gained an `actions: list
[Action]` field, computed independently of whichever provider (mock or a
real LLM) generated the reply text - the same separation of concerns
already used for the booking-flow facts. `TestChatResponse.actions`
(`schemas.py`) carries this to the frontend; `TestChatRequest.action_id`
(new, optional) carries a button click back to the backend.

**Frontend**: `Message`/`TestChatResponse` gained `actions` (`lib/
types.ts`). `MessageBubble.tsx` renders them as a stacked column of
rounded, bordered, white buttons attached directly below the agent's
bubble (not a separate global component). Clicking one calls the exact
same send path as typing (`handleSend(label, action_id)`), so a click and
typing the same label produce byte-identical backend behavior. The
now-unused `QuickActionsBar.tsx`, `ServiceDropdown.tsx`, and
`QuickReplyChips.tsx` components, and the now-superseded `lib/
constants.ts` (a hand-maintained duplicate of the action/service catalog)
were deleted rather than left as dead code - the backend is now the sole
source of truth for what actions exist and what they're labeled.

## 6. Action IDs used

Main menu: `book_pickup`, `track_order`, `change_pickup_time`,
`add_more_items`, `cancel_order`, `call_support`.

Service selection: `wash_and_fold`, `dry_cleaning`, `ironing`,
`blankets_duvets`, `curtains_upholstery`, `business_laundry`,
`other_cleaning`.

## 7. Welcome message behavior change

Previously, a vague opener like "I need laundry" or "I need help" was
treated as an implicit booking request and jumped straight to "which
service do you need?". Per explicit instruction, these (plus "Hi",
"Hello", "What services do you offer?") now show the fixed welcome
message ("Hi 👋 Welcome to LaundryKhalas. How can we help you today?")
with the 6 main-menu buttons attached, and the booking flow only starts
once the customer picks "Book Pickup" (or types something with a clear
booking signal, e.g. "book a pickup", "how much for dry cleaning"). A new
`booking_in_progress` check in `agent.py` (true once any slot - service,
area, or time - is already known from earlier in the conversation) means
an ambiguous reply mid-booking doesn't derail back to the welcome screen;
only a genuinely fresh/unclear message does.

The out-of-domain refusal was also updated to match: "Sorry, I can only
help with LaundryKhalas laundry and cleaning services. How can we help
you today?" with the main menu re-attached, so a rejected off-topic
question always leaves the customer with a clear way forward instead of a
dead end.

## 8. Current mock behavior (all flows)

Every quick-action flow (Track/Cancel/Change/Add Items/Call Support) is
unchanged in substance from the prior build, only the button-attachment
mechanism and exact copy changed to match this task's specified wording.
All remain explicitly demo/mock-labeled:

- Track Order: asks for an Order ID, echoes it back with
  `" (Demo mode — not connected to a live order system yet.)"` - never
  claims to have found a real order.
- Cancel Order: asks for an Order ID, explicitly states the team will
  confirm whether it can still be cancelled - never claims cancellation
  happened.
- Change Pickup Time: asks for both Order ID and new time, echoes both
  back, demo-labeled - never claims the change is confirmed.
- Add More Items: asks what items, then acknowledges exactly what was
  typed, demo-labeled.
- Call Support: gives a handoff message with
  `" (Demo mode — not connected to a live support team yet.)"` - never
  claims a real connection was made.

There is still no `Order` model anywhere in this standalone codebase (see
architecture doc) - none of the above could be made to "actually work"
without that being built first.

## 9. What will be needed later for real WhatsApp Cloud API interactive messages

Everything here (`Action`, `actions` on the response) is this app's own
JSON shape - **not** Meta's interactive-message format. Before this could
drive real WhatsApp buttons via the Cloud API webhook path
(`api/webhooks.py`, currently text-only), still needed:

- Send-side: Meta's `interactive` message type (`button` for ≤3 options,
  `list` for more - the 6-item main menu and 7-item service menu both
  exceed the 3-button limit, so both would need the `list` format, not
  `button`) - `channels/meta_whatsapp.py`'s `send_text()` only sends plain
  text today.
- Receive-side: Meta's webhook payload for a list/button reply arrives as
  an `interactive` message type with a different JSON shape than a plain
  text message - `parse_inbound_webhook()` only extracts `type ==
  "text"` today and would need a second branch.
- A real `Order` model, so Track/Cancel/Change/Add-Items could act on
  something real instead of echoing back an unvalidated ID - see the
  cross-referenced decision needed in `docs/checklists/
  live-whatsapp-readiness.md` about which system (this one or the main
  system) becomes the real integration.

## 10. Files changed

**Backend**: `agents/whatsapp_agent/actions.py` (new),
`agents/whatsapp_agent/agent.py`, `agents/whatsapp_agent/tools.py`
(pending-action marker strings updated to match new copy),
`llm/providers/mock.py`, `services/domain_guard.py` (refusal text),
`schemas.py`, `api/chat.py`, `tests/test_quick_actions.py` (rewritten).

**Frontend**: `lib/types.ts`, `lib/api-client.ts`,
`components/MessageBubble.tsx`, `app/chat/page.tsx`,
`components/Composer.tsx` (leftSlot removed), `components/DebugPanel.tsx`
(actions row added). Deleted: `components/QuickActionsBar.tsx`,
`components/ServiceDropdown.tsx`, `components/QuickReplyChips.tsx`,
`lib/constants.ts`.

## 11. Bugs found and fixed during this build

- **Stale marker strings broke multi-turn order flows.** The wording
  changes to match this task's exact copy (e.g. "share your order ID so I
  can help you check the status" → the old marker string
  `"share your order id so"` no longer matched) silently broke
  `tools.pending_order_action()`'s follow-up detection for Track Order and
  Change Pickup Time - a reply like "LK-1023" fell through to the welcome
  menu instead of continuing the flow. **Fixed**: updated all four marker
  substrings to match the current exact wording, verified against the
  live API for all three affected flows (Track, Change, Add Items).
- **"What services do you offer?" didn't get the welcome message.** Since
  it's a genuine question ending in "?", it classified as
  `unanswerable_question`, which initially kept its own distinct "good
  question, team will confirm" reply instead of the welcome+menu the task
  explicitly lists it under. **Fixed**: merged `unanswerable_question`
  into the same welcome-menu fallback as `unknown_laundry_related` -
  removed the now-dead branch in `mock.py`. Caught by a parametrized test
  that explicitly checks this exact phrase.

## 12. Tests run and results

`docker run --rm whatsapp-agent-standalone python -m pytest tests -v` -
**95 passed, 0 failed** (was 88; `test_quick_actions.py` rewritten with 19
tests covering welcome/menu behavior, action-id-based routing for every
flow, and the no-live-claim guarantees). Frontend: `npm run typecheck`
(clean), `npm run lint` (0 warnings), `npm run build` (succeeds, 3 routes).

End-to-end manual verification (live containers): "Hi" → welcome + 6
buttons → click Book Pickup (`action_id: book_pickup`) → "Great. Which
service do you need today?" + 7 service buttons → click Dry Cleaning
(`action_id: dry_cleaning`) → "Perfect. Please share your pickup area or
address." (no buttons) → "Dubai Marina, tomorrow 6pm" → booking
confirmation. Matches the task's example flow exactly.

## 13. Known limitations

- **Actions are not persisted.** Reloading a conversation shows the full
  message history but only the message from the *live* response carries
  its buttons - older agent bubbles lose their buttons on reload (all
  flows still work via free text as a fallback). This was a deliberate
  scope decision to avoid a database migration for a UI-only convenience
  in a standalone MVP - documented here rather than silently accepted.
- Still mock-only throughout; still no real Meta interactive-message
  integration (see §9); still no `Order` model.
- A real browser walkthrough of the new bubble-attached buttons (visual
  layout, stacking with many options, hover state) has not been done in
  any session - only HTTP/API-level verification and a build/typecheck/
  lint pass.

## 14. Next recommended step

1. A human browser walkthrough of the new interactive-button layout -
   still the one verification gap across every round of this standalone
   agent's development.
2. Founder/team decision on the Order-model / real-Meta-integration
   questions already flagged in `docs/checklists/
   live-whatsapp-readiness.md` and prior build reports - unchanged by this
   task.
3. Otherwise, resume the main roadmap (`CLAUDE.md` §18).
