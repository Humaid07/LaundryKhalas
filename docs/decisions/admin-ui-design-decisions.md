# Admin UI Design Decisions

- The admin UI (`apps/admin/`) is for LaundryKhalas's internal operations
  team only - it is not customer-facing and is not the future
  customer/driver app.
- The first UI built focuses entirely on visually testing the WhatsApp
  Operations Agent MVP: conversations, mock orders, the approval queue,
  and AI action logs. Nothing else.
- The UI is mock-first and must always visibly communicate that it is
  mock-first - see the persistent "Mock Environment" indicator in
  `components/layout/AdminTopbar.tsx` and the explicit button copy
  ("Approve Mock Reply", "Send Manual Mock Reply", "Simulate Inbound
  Message") used throughout.
- `D:\LaundryKhalas\LaundryKhalaasPrototype` was reviewed for layout/UX
  ideas only (see `docs/audits/admin-ui-start-report.md`). No prototype
  code, styling tokens, or components were copied - the new UI is a fresh
  implementation with its own neutral, meaning-driven color system
  (`tailwind.config.ts`).
- The new UI is intentionally cleaner and more restrained than the
  prototype: a flat sidebar with a single active-state treatment (no
  gradients), only 6 nav items that are all real and backend-wired (vs.
  the prototype's 20 items, most backed by static mock arrays), and no
  decorative numeric badges that aren't computed from real data.
- No live WhatsApp, Stripe, or LLM integration exists or is referenced
  anywhere in the UI - the topbar explicitly shows all three as "Off."
- Classifier UI (intent/sentiment/urgency management) is deferred until
  the classifier agent itself is built - `Conversation.latest_intent` etc.
  are placeholder fields today and are not surfaced as editable/manageable
  in this UI.
- SEO/marketing UI is out of scope entirely - not referenced anywhere.
- Driver app and customer-facing app UI are out of scope entirely - not
  referenced anywhere in this admin tool.
