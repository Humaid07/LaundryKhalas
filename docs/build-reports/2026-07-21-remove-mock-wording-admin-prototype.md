# Build Report — Remove "mock/demo" wording from the /admin prototype UI

**Date:** 2026-07-21

## 1. Task objective
Owner request: "remove words like mock, demo environment etc from the dashboard to make it look more professional." A prior pass (`2026-07-21-remove-mock-demo-copy.md`) cleaned the new **Command Center dashboard** (`app/(dashboard)`, `components/dashboard`). This pass removes the remaining **visible** throwaway wording from the older `/admin` **WhatsApp-agent prototype**, which was still surfacing "Mock", "Simulate", etc.

## 2. What was built
Text-only copy changes across the `/admin` prototype so the visible UI reads production-ready, plus a display override for the `mock_sent` message status. No behaviour, routing, data, or integrations changed — the system stays fully mock/staged underneath.

## 3. Why
The `/admin` prototype is demoed alongside the Command Center. Visible words like "Mock Environment", "Approve Mock Reply", "Simulate Inbound Message" made a finished product look like a throwaway test. Aligns the prototype with the owner-approved vocabulary already used in the dashboard (Staged / Review Mode / Operational).

## 4. Files modified
- `apps/admin/components/layout/AdminTopbar.tsx` — badge "Mock Environment" → "Review Mode".
- `apps/admin/components/layout/AdminSidebar.tsx` — nav label "Mock WhatsApp Console" → "WhatsApp Console"; footer "Internal operations tool. Mock-first WhatsApp Agent testing only." → "Internal operations console for the WhatsApp Agent."
- `apps/admin/components/approvals/ApprovalCard.tsx` — "Approve Mock Reply" → "Approve Reply".
- `apps/admin/components/conversations/ChatMessageBubble.tsx` — "Approve Mock Reply" → "Approve Reply".
- `apps/admin/components/conversations/ManualReplyBox.tsx` — placeholder + button: "…manual mock reply" → "…manual reply".
- `apps/admin/app/admin/page.tsx` — "Mock orders created" → "Orders created"; "Mock outbound messages sent" → "Outbound messages sent"; hint "…via mock adapter" → "…to the customer"; empty state "Simulate an inbound message…" → "Send an inbound message…"; "Recent mock orders" → "Recent orders".
- `apps/admin/app/admin/orders/page.tsx` — description "Mock orders created by…" → "Orders created by…".
- `apps/admin/app/admin/mock-whatsapp/page.tsx` — title "Mock WhatsApp Test Console" → "WhatsApp Console"; description reworded (drops "mock", keeps honest "No live WhatsApp message is sent"); heading + button "Simulate Inbound Message" → "New Inbound Message" / "Send Inbound Message".
- `apps/admin/app/admin/conversations/page.tsx` — description + empty state reworded to drop "mock channel" / "Simulate … Mock WhatsApp Console".
- `apps/admin/components/ui/status-badge.tsx` — added `STATUS_LABEL` override so the backend `mock_sent` status renders as "Sent" (the status key is unchanged).

## 5. What is mock-only / live
No change. All live integrations remain **off** (Live WhatsApp / Stripe / LLM). This is cosmetic copy only; nothing was connected to match the wording.

## 6. Intentionally deferred (not user-visible)
- Route path `/admin/mock-whatsapp` (URL only — visible label is now "WhatsApp Console"). Renaming the folder/route touches links and is out of scope for a copy pass.
- Code comments, import paths, and the `mock-data.ts` filename / `mode: "mock" | "live"` API type — not rendered to users.
- The word "MVP" in the overview description was left as-is (common professional term, outside the mock/demo request).

## 7. Tests run
- `npx tsc --noEmit` in `apps/admin` → **exit 0** (passes).
- Did not run `next build` (known Windows 500.html rename quirk) and did not touch a running dev server.

## 8. Known limitations
Static build artifacts under `apps/admin/.next-verify` still contain the old strings; they are stale output and regenerate on next build.

## 9. Next recommended step
Optional: consider whether "MVP" in the `/admin` overview description should also be softened for investor demos.
