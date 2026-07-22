This repo must be treated as the source of truth. Previous Claude chats may not be available. Before any major work, read docs/00-Home.md, docs/build-reports, docs/architecture, docs/checklists, and current app structure.

LaundryKhalas — Claude Project Memory \& Engineering Rules
---

## 1\. Project Identity

LaundryKhalas is a laundry and cleaning marketplace operating through a WhatsApp-first customer experience.

The long-term system is not just a chatbot. It is an Agentic LLM Operating System for:

* Customers
* LaundryKhalas internal operations team
* Partner cleaning facilities
* Drivers later
* Admin dashboards
* Approval workflows
* Reporting
* Marketing/SEO agents later
* Multi-market expansion across UAE, Qatar, GCC, and beyond

The first business module is the WhatsApp Operations Agent.

## 2\. Current Build Priority

The current priority is:

1. WhatsApp Operations Agent
2. Admin dashboard UI for visually testing the agent
3. Approval/reject/manual takeover workflow
4. Mock order creation
5. Mock facility assignment
6. AI action logging
7. Clean weekly documentation and presentation-ready reports

Do not jump ahead to future modules unless explicitly asked.

## 3\. Existing Prototype Context

There is an older prototype at:

D:\\LaundryKhalas\\LaundryKhalasPrototype

Use it only as product and UI reference.

It may be used to understand:

* Admin layout
* Dashboard ideas
* Conversation/chat flows
* Order concepts
* Mock data ideas
* UI/UX direction
* Mistakes to avoid

Do not blindly copy the prototype.

Do not copy secrets, .env files, hardcoded demo logic, broken architecture, or insecure shortcuts.

The new project is the source of truth.

## 4\. Core Architecture Decisions

Backend:

* Python 3.11+
* FastAPI
* SQLAlchemy async
* Alembic
* Pydantic v2

Database:

* PostgreSQL
* pgvector
* PostGIS
* uuid-ossp
* PostgreSQL remains the source of truth

Queue/cache:

* Redis
* Celery worker
* Celery beat

Agent orchestration:

* LangGraph

LLM:

* Internal llm\_service only
* MockProvider first
* AnthropicProvider later behind config
* OpenAIProvider later behind config
* No direct SDK calls outside llm\_service
* No live LLM calls unless explicitly approved

WhatsApp:

* MockWhatsAppAdapter first
* Future live provider: official Meta WhatsApp Cloud API
* Own phone numbers per market/region
* No Respond.io or Wati hard dependency
* No unofficial WhatsApp automation

Frontend:

* React / Next.js
* TypeScript
* Tailwind CSS
* shadcn/ui or clean equivalent components
* Clean internal SaaS dashboard style

Cloudflare direction:

* Cloudflare-first direction later
* Cloudflare Pages/Workers for frontend/admin/customer web later
* Cloudflare Workers as edge/webhook gateway later
* Cloudflare Containers may be evaluated for FastAPI later
* Cloudflare R2 for files/photos later
* Cloudflare AI Gateway later
* Cloudflare Queues/Workflows later if needed
* Do not use Cloudflare D1 as core database
* Do not use MySQL as core database

## 5\. Non-Negotiable Engineering Rules

Every build must follow these rules:

1. Mock-first by default.
2. No live WhatsApp unless explicitly approved.
3. No live Stripe unless explicitly approved.
4. No live Anthropic/OpenAI unless explicitly approved.
5. No live external API calls unless explicitly approved.
6. No secrets committed.
7. No invented operational data.
8. No invented prices, policies, discounts, refund rules, facility details, turnaround promises, or availability.
9. Database/config is the source of truth.
10. Every agent action must be logged.
11. Every tool call must be logged.
12. Every approval/rejection must be logged.
13. Every risky action requires human approval.
14. Privacy firewall must be respected.
15. Keep the system staged and testable.
16. Build the smallest safe working version first.
17. Do not overbuild.

## 6\. Risky Actions Requiring Human Approval

Agents cannot autonomously:

* Refund
* Compensate
* Cancel outside policy
* Give discounts beyond configured limits
* Resolve complaints with commitments
* Promise exact turnaround unless configured
* Assign blame to facility/driver/customer
* Contact facility directly without proper flow
* Contact driver directly without proper flow
* Make legal, medical, unsafe, or unverifiable claims
* Send live WhatsApp messages without approval in MVP

For MVP, every agent-generated customer reply requires admin approval.

## 7\. Privacy Firewall

Never expose unnecessary PII.

Before sending context to an LLM:

* Mask phone numbers
* Mask emails
* Avoid full customer addresses unless required
* Use area/city instead of full address where possible
* Avoid sending raw private data if not needed

Facility-facing or driver-facing outputs must not include:

* Customer phone number
* Customer email
* Full address unless operationally required and role-authorized
* Sensitive notes
* Internal AI reasoning
* Payment information

## 8\. WhatsApp Agent Rules

The WhatsApp Operations Agent handles only safe happy-path operations first.

Supported MVP behavior:

* Receive mock WhatsApp-style message
* Store customer/conversation/message
* Read conversation context
* Ask for missing service type
* Ask for missing pickup area/address
* Ask for preferred pickup time
* Get configured mock price from DB/config
* Create mock order
* Assign mock facility
* Draft customer reply
* Create approval request
* Wait for admin approval
* Store approved mock outbound message

The agent must not:

* Process refunds
* Process payments
* Cancel orders autonomously
* Resolve complaints autonomously
* Promise exact delivery unless configured
* Invent data
* Send live WhatsApp messages

## 9\. Classifier Agent Status

The classifier agent is a separate future module.

The classifier should eventually run before the WhatsApp Operations Agent.

Classifier responsibilities later:

* intent
* sentiment
* urgency
* complaint flag
* angry flag
* escalation flag
* refund/cancellation detection
* B2B enquiry detection

Do not build classifier unless explicitly asked.

When classifier is not built, document placeholders clearly.

## 10\. Admin UI Rules

The admin UI is for internal operations testing.

It must be:

* clean
* professional
* SaaS-like
* easy for non-technical staff
* visually better than the old prototype
* mock-mode clear
* simple to demo
* suitable for weekly reporting

Admin UI must support:

* overview dashboard
* conversations inbox
* conversation detail/chat view
* mock WhatsApp test console
* approval queue
* orders list
* order detail
* AI action logs
* manual takeover
* approve/reject agent drafts

Every page must have:

* clear title
* loading state
* empty state
* error state
* refresh option where useful
* consistent buttons
* consistent badges
* responsive layout
* no broken links
* no console errors

Mock mode must always be visible.

Use labels like:

* MOCK ENVIRONMENT
* Live WhatsApp: Off
* Live Stripe: Off
* Live LLM: Off
* Approve Mock Reply
* Send Manual Mock Reply
* Simulate Inbound Message

## 11\. Documentation Is Mandatory

No task is complete until documentation is updated.

Every major task must generate clean documentation that can be used for:

* weekly report
* founder/team update
* presentation
* Gamma/PPT slides
* Obsidian vault reference
* technical handover

Documentation must be:

* clear
* structured
* easy to read
* concise but complete
* honest about what works and what is missing
* Obsidian-friendly Markdown

Use this docs structure:

docs/
00-Home.md
weekly-reports/
build-reports/
audits/
architecture/
decisions/
checklists/
presentation-notes/

## 12\. Required Docs After Every Major Task

After every major task, create:

docs/build-reports/YYYY-MM-DD-task-name.md

The build report must include:

1. Build title
2. Date
3. Task objective
4. What was built
5. Why it was built
6. Files created
7. Files modified
8. API endpoints added/changed
9. Database tables/models added/changed
10. UI pages/components added/changed
11. Agent behavior added/changed
12. Integrations added/changed
13. What is mock-only
14. What is live
15. What is intentionally deferred
16. Tests run
17. Test results
18. Bugs/issues found
19. Known limitations
20. Security/privacy notes
21. Cost/LLM usage notes
22. Screens/pages to demo
23. Commands to run
24. How to verify manually
25. Next recommended step

Also update:

docs/weekly-reports/week-XX-report.md

Include:

1. Executive summary
2. What shipped this week
3. What changed since last update
4. Screens/features ready to demo
5. Backend progress
6. Frontend progress
7. Agent progress
8. Database progress
9. Security/privacy progress
10. Testing progress
11. Blockers
12. Risks
13. Decisions needed from founder/team
14. Deviations from roadmap/spec
15. Next week's plan

Also update:

docs/presentation-notes/week-XX-presentation-notes.md

Include:

1. What we can show in the demo
2. Suggested demo flow
3. Screenshots needed
4. Talking points
5. Technical explanation in simple language
6. Business value
7. Before vs after
8. Risks or caveats to mention honestly
9. What is coming next

Also update:

docs/00-Home.md

Add links to latest:

* build report
* weekly report
* presentation notes
* key architecture docs
* key decision docs

Use Obsidian-style links where useful.

Examples:

\[\[whatsapp-agent-architecture]]
\[\[admin-ui-architecture]]
\[\[live-whatsapp-readiness]]
\[\[week-01-report]]

## 13\. Completion Summary Required

At the end of every task, report:

1. Code completed
2. Documentation completed
3. Build report path
4. Weekly report path
5. Presentation notes path
6. Tests run
7. Test results
8. What is ready to demo
9. What is not ready
10. What is deferred
11. Risks/blockers
12. Next recommended task

If documentation was not updated, the task is not complete.

## 14\. Testing Rules

Every task should include appropriate testing.

At minimum:

* run backend tests if backend changed
* run frontend build/typecheck/lint if frontend changed
* verify Docker Compose if infra changed
* verify migrations if DB changed
* verify no live external calls are made
* verify no secrets are committed
* document test results honestly

Do not claim tests passed unless they actually ran.

If tests cannot run, document why.

## 15\. Git Safety Rules

Before making changes:

* check current git status
* do not overwrite uncommitted work
* do not delete existing important files without explanation
* avoid large unrelated refactors
* keep changes scoped to the task
* document risky changes

For experimental work:

* use a separate branch
* do not merge into main without review
* do not deploy production unless explicitly asked

## 16\. Build Discipline

For every new task:

1. Inspect existing repo first.
2. Inspect relevant old prototype only if useful.
3. Create/update audit or start report.
4. Plan implementation.
5. Implement small safe changes.
6. Run tests/checks.
7. Update documentation.
8. Provide completion summary.

Do not start coding blindly.

## 17\. Deferred Modules

Do not build these unless explicitly requested:

* classifier agent
* SEO agents
* marketing agents
* driver app
* customer mobile app
* live WhatsApp
* live Stripe
* live LLM integrations
* Cloudflare production deployment
* full 14-market automation
* autonomous refund/complaint handling

## 18\. Current Roadmap Direction

Current staged order:

1. WhatsApp Agent backend foundation
2. Admin UI for visual testing
3. Classifier Agent
4. Stronger approval/manual takeover
5. Live WhatsApp readiness
6. Stripe mock/payment flow
7. Driver/VDP backend
8. Reporting and intelligence
9. SEO/marketing agents
10. Cloudflare staging/production deployment

Follow this order unless the founder/team explicitly changes priority.

## 19\. UI Design Standard

All UI should feel like a premium internal operations SaaS.

Use:

* clean layout
* subtle borders
* professional spacing
* readable typography
* status chips
* compact tables
* elegant cards
* modern sidebar
* clear empty/loading/error states

Avoid:

* messy alignment
* excessive gradients
* childish colors
* huge random cards
* cluttered dashboards
* unclear button labels
* demo-looking fake UI

## 20\. Always Be Honest

Always clearly state:

* what works
* what does not work
* what is mock-only
* what is live
* what was deferred
* what requires founder/team decision
* what risks exist
* what tests were actually run

Never pretend something is complete if it is not.

End of CLAUDE.md content.

