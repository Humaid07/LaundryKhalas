# Week 1 — Classifier Agent Demo Notes

Companion to `docs/build-reports/2026-07-18-classifier-agent.md`. Written
for a founder/team presentation, not a technical audience.

## 1. Why the classifier agent matters

Until now, the system could see that a message arrived, but had no idea
whether it was a happy new customer, an angry one, a business lead, or
someone trying to cancel - every message was treated the same way. The
Classifier Agent reads every incoming message and labels it: what does the
customer want (intent), how do they feel (sentiment), does this need urgent
attention (urgency/escalation flags), is this a complaint, is this a
business enquiry. This is the foundation for routing the right conversation
to the right place before more automation is layered on top.

## 2. How the team can test it

No dedicated classifier UI page yet, but no need to wait for one - three
ways to see it work today, no new code required:

1. **AI Action Logs page** (`/admin/ai-logs`, already exists in the Admin
   UI) - every classification shows up here automatically, since it's a
   generic viewer over the same `AIActionLog` table every agent writes to.
   Look for rows with `agent_name: classifier_agent` (an `llm_complete` row
   plus a `classify` row per message) and expand the JSON viewer to see the
   full intent/sentiment/routing-flag result.
2. **It runs automatically on every message.** Every message sent through
   the existing Mock WhatsApp Test Console (`/admin/mock-whatsapp`) is
   classified the moment it arrives - open any conversation afterward
   (`/admin/conversations/[id]`) and the raw API response
   (visible via browser dev tools or `/docs`) shows `latest_intent`,
   `latest_sentiment`, `latest_urgency` populated on the conversation.
3. **Direct API testing** via `/docs` (FastAPI's auto-generated page) or
   curl - simulate an inbound message, then call
   `POST /api/admin/conversations/{id}/classify` to see the full
   classification result, or `GET /api/admin/ai-action-logs?conversation_id=`
   to see the full audit trail.

Example tried live during this build: the message "This is unacceptable,
my order was cancelled without telling me, I am furious" was correctly
classified as `intent: complaint`, `sentiment: angry`, `urgency: urgent`,
with `is_escalated` and `complaint_flag` both true.

## 3. What it actually classifies

- **Intent** - 18 categories, e.g. `quote_request`, `complaint`,
  `cancellation`, `b2b_lead`, `pickup_issue`.
- **Sentiment** - `happy / neutral / frustrated / urgent / angry`, plus a
  -1.0 to +1.0 numeric score.
- **Routing flags** - is this urgent? escalated? a complaint? does the
  customer sound angry? is this a refund/cancellation? is this a B2B
  enquiry? All computed automatically per message.
- **Sales-stage delta / topic** - a short label for what changed in the
  conversation's stage, and a 2-5 word topic summary.

## 4. How this fits with the rest of the system

**Update, same day:** this is now wired together. The classifier runs
first (automatically, on every inbound message); then, when an admin
clicks "Run WhatsApp Agent," the Operations Agent checks what the
classifier found *before* doing anything else. If the message was flagged
as a complaint, cancellation, rescheduling, payment issue, B2B enquiry, or
otherwise urgent/angry, the Operations Agent skips its normal pickup-order
flow entirely and routes straight to human escalation instead - see
`docs/build-reports/2026-07-18-classifier-escalation-wiring.md`.

This closed a real gap found while wiring it up: a message like "please
reschedule my wash and fold pickup to tomorrow, Marina" contains everything
the Operations Agent normally looks for (service, area, time) - without
this check, it would have quietly created a **second, duplicate order**
for a customer who was actually trying to change their existing one. Now
it recognizes the rescheduling intent and escalates to a human instead.

## 5. What is still mock-only

- The classification logic itself is deterministic keyword-matching
  today, not a live AI model call - same "mock-first" posture as
  everything else in this system. It's good enough to demo the concept and
  the full pipeline (message in → labeled → audited) reliably and
  repeatably, but it will occasionally miss nuance a real language model
  would catch (sarcasm, indirect complaints, etc.).
- The real AI prompt for this task is already written and ready to go -
  turning it on is a small, contained change once a live LLM provider is
  approved (`CLAUDE.md` requires explicit approval before that happens).
- No live WhatsApp, no live payment, no live AI model calls anywhere in
  this task - consistent with every other module in this build.

## 6. What must happen before this is customer-facing

- A small Admin UI addition so staff can actually see these labels at a
  glance (currently only visible via the raw API) - a badge or filter on
  the conversations list.
- Eventually, enabling a real AI model for classification (with founder
  approval), since keyword matching alone won't be reliable enough for
  production traffic diversity.
- Everything in `docs/checklists/live-whatsapp-readiness.md` still applies
  before any of this touches a real WhatsApp number.

## 7. Talking points

- "Every message that comes in now gets automatically triaged - we know
  immediately if something needs urgent human attention, even before a
  staff member opens the conversation."
- "This is the same audit-everything discipline as the rest of the system -
  every classification decision is logged with full detail, nothing is a
  black box."
- "The labeling logic today is a fast, deterministic first pass. The real
  AI-powered version is already written and ready - we're one approved
  config change away from turning it on."

## 8. Before vs after

Before: every inbound message was treated identically regardless of
content or tone - an angry complaint and a routine pickup request looked
the same to the system.
After: every message is automatically triaged on arrival, with urgency and
complaint signals available immediately, ahead of any other automation
touching that conversation.

## 9. What is coming next

Per `CLAUDE.md` §18: stronger approval/manual-takeover workflow, then live
WhatsApp readiness work. The two follow-ups flagged specifically by this
task (Operations Agent reacting to classifier flags; a small Admin UI
surface for the labels) are recommended before those, but not yet
scheduled - a founder/team call.
