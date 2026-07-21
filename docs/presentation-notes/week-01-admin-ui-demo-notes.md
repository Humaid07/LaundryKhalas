# Week 1 — Admin UI Demo Notes

Companion to `docs/build-reports/2026-07-18-admin-ui-build.md`. Written for
a founder/team presentation, not a technical audience.

## 1. Why the admin dashboard matters

Until now, the only way to see the WhatsApp Operations Agent work was
`curl` commands against the API or the auto-generated `/docs` page — not
something anyone outside engineering could look at or trust. The admin
dashboard is the first screen anyone (technical or not) can open, click
through, and see the agent actually do its job: read a message, ask a
follow-up if it's missing information, price a job, create a mock order,
assign a mock facility, and hand its draft reply to a human for approval.

It's also the foundation for two things the business needs regardless of
which LLM/WhatsApp provider we end up on: a human-in-the-loop approval
workflow (nothing goes to a customer without a person clicking "approve"),
and a full audit trail of every action the agent took and why.

## 2. How the team can test WhatsApp conversations

No real WhatsApp number or phone is needed yet — everything runs through a
**Mock WhatsApp Test Console** built into the dashboard:

1. Open `http://localhost:3000/admin`.
2. Go to **Mock WhatsApp Test Console**.
3. Pick a market (e.g. `AE`), type a phone number, and either type a
   message or click one of the quick-fill sample messages (e.g. "I need
   laundry pickup tomorrow").
4. Click **Simulate Inbound Message** — this behaves exactly like a real
   incoming WhatsApp message would once we're live, just without touching
   Meta's API.
5. Open the conversation it created, click **Run WhatsApp Agent**, and
   watch it either ask a follow-up question (if info is missing, e.g. no
   pickup area) or draft an order confirmation with a real seeded price and
   facility.

This was re-run live today with the message "I need laundry pickup
tomorrow, Dubai Marina" — the agent correctly priced it at AED 25.00 and
assigned the seeded Dubai Marina facility, with nothing invented.

## 3. How approval / reject / manual takeover works

- **Every** draft reply the agent writes lands in the **Approval Queue**
  before a customer would ever see it — this is a hard rule (`CLAUDE.md`
  §6), not a UI preference. The MVP does not let the agent send anything
  unsupervised.
- On the Approval Queue page, a staff member reviews the draft text next to
  the conversation it came from and clicks **Approve Mock Reply** or
  **Reject**. Approving marks the mock message as sent; rejecting discards
  it — nothing is silently retried.
- **Manual Takeover**, on the conversation page, lets a human pause the
  agent entirely and reply directly (**Send Manual Mock Reply**) — useful
  for complaints, refunds, or anything outside the agent's safe happy-path
  scope, none of which the agent is allowed to handle on its own (`CLAUDE.md`
  §6/§8). Manual replies skip the approval queue by design, since a human
  already wrote them.
- Every one of these actions — the agent's tool calls, its draft, the
  approval/rejection, the manual reply — is written to the **AI Action
  Logs** page with full input/output detail, so nothing happens invisibly.

## 4. What is still mock-only

Everything, end to end. The topbar has a permanent "Mock Environment"
banner plus explicit "Live WhatsApp: Off / Live Stripe: Off / Live LLM:
Off" indicators so nobody mistakes a demo screenshot for a live system.
Concretely:

- Messages are simulated through the console, not sent/received via Meta's
  WhatsApp Cloud API.
- Orders and facility assignments are created against seeded mock data, not
  real facility contracts.
- No payment is processed anywhere in this flow.
- The LLM call the agent makes uses this environment's configured (non-live
  by default) provider — no live Anthropic/OpenAI call was made in today's
  verification pass.

## 5. What must happen before live WhatsApp

Tracked in detail in `docs/checklists/live-whatsapp-readiness.md`; the
highlights relevant to what this dashboard shows today:

- Real per-user admin authentication/roles — today it's a single shared API
  key for all admin actions, fine for an internal testing tool, not for
  production.
- A live WhatsApp Cloud API adapter to replace `MockWhatsAppAdapter` —
  none of today's demo touches Meta's API.
- Explicit, approved enablement of a live LLM provider — currently
  mock/config-driven by design (`CLAUDE.md` §4).
- The customer-detail gap noted in engineering (no way yet to resolve a
  customer ID to a name/phone in the UI) should be closed before this is
  used for real customer conversations.
- A full manual click-through in an actual browser (verified so far only
  at the HTTP/API level, plus a clean typecheck/lint/production-build —
  see the build report's Tests Run section) should happen before showing
  this live to anyone outside the immediate team.

## 6. Suggested demo flow (~5 minutes)

1. Open Overview — point out the mock-environment badge.
2. Mock WhatsApp Test Console — simulate an inbound pickup request.
3. Open the conversation, click Run Agent — show the drafted reply.
4. Approval Queue — approve it live.
5. Back in the conversation — show the mock "sent" reply.
6. Orders — open the created order, show the timeline and assigned mock
   facility.
7. AI Action Logs — expand one row to show the full tool-call trail.
8. (Optional) Trigger Manual Takeover on a second conversation and send a
   manual reply, to show the human-override path.

## 7. Screenshots needed

(Not captured in this session — no browser automation tool was available.
A human should capture these before an external presentation.)

- Overview page with the mock-environment badge visible.
- Mock WhatsApp Test Console mid-fill.
- Conversation detail showing an inbound bubble + agent draft bubble.
- Approval Queue with a pending item.
- Order detail with timeline.
- AI Action Logs with one row expanded.

## 8. Talking points

- "Nothing here can accidentally message a real customer, charge a real
  card, or call a real AI provider — every one of those is off by default
  and requires explicit approval to turn on."
- "Every reply the AI drafts is reviewed by a person before it goes out —
  that's not a v2 feature, it's how the MVP is built."
- "We can already see the full reasoning trail — every tool call, every
  price lookup, every facility assignment — which is what we'll need for
  support/QA once this is live."

## 9. Business value

Gives non-engineers a way to see and trust the agent's behavior before any
real customer is exposed to it, and gives the team a repeatable way to
regression-test agent behavior (new prompts, new markets, new pricing)
without writing code.

## 10. Before vs after

Before: agent behavior only verifiable via raw API calls or automated
tests — not demoable to a founder or non-technical stakeholder.
After: a clickable, professional-looking internal tool that exercises the
exact same backend, with a visible safety net (approval queue, manual
takeover, mock-mode indicators) built in from day one.

## 11. Risks or caveats to mention honestly

- This was built and is being demoed on `localhost` only — nothing is
  deployed anywhere shared yet.
- No automated frontend tests exist yet, but `npm run typecheck`/`lint`/
  `build` were run today (via the built Docker image) and all passed —
  see the build report §16/§17 for exactly what was and wasn't verified.
  A real browser walkthrough is still the one outstanding check.
- A stale Docker dev-cache issue caused two pages to briefly 500 during
  today's verification pass; a container restart fixed it and it's
  documented, but flag it if anyone hits a 500 during the live demo — the
  fix is a container restart, not a data problem.
- Single shared admin API key, not per-user login — fine for internal
  testing, not for a wider rollout.

## 12. What is coming next

Per `CLAUDE.md`'s staged roadmap (§18): stronger approval/manual-takeover
UX hardening, then the Classifier Agent (intent/sentiment/urgency), then
live WhatsApp readiness work — in that order, not started until explicitly
requested.
