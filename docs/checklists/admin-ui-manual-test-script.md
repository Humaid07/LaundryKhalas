# Admin UI Manual Test Script

Follow these steps in order to exercise the full WhatsApp Agent MVP flow
through the new admin UI.

1. Start the backend: `cd "D:\Laundry Khalas App" && docker compose up -d postgres redis api celery_worker celery_beat` (or `docker compose up --build` for everything, including the UI - see step 2).
2. Start the frontend: `docker compose up -d admin` (or `docker compose up --build` to build+start everything at once). Confirm both are reachable: `http://localhost:8000/health` returns `{"status":"ok"}`, `http://localhost:3000` redirects to `/admin`.
3. Open **`http://localhost:3000/admin`**. Confirm the Overview page loads with stat tiles (likely all zero on a fresh DB) and the "Mock Environment" badge is visible in the topbar.
4. Go to **Mock WhatsApp Test Console** (`/admin/mock-whatsapp`).
5. Fill in Market = `AE`, a phone number, and send: **"I need laundry pickup tomorrow."** (or click the matching quick-fill button). Click **Simulate Inbound Message**.
6. Confirm the Result panel shows a success card with an **"Open conversation"** link. Click it.
7. On the Conversation Detail page, confirm the inbound message bubble appears on the left. Click **Run WhatsApp Agent**.
8. Confirm an **"Agent Draft — Pending Approval"** bubble appears on the right with either a follow-up question or an order confirmation, depending on whether the message had enough info (service type / area / pickup time).
9. Go to **Approval Queue** (`/admin/approvals`). Confirm the same draft appears under the "Pending" tab with the conversation link.
10. Click **Approve Mock Reply**.
11. Return to the conversation (via the link on the approval card, or the inbox). Confirm the draft bubble is gone and a new outbound message bubble appears with status `mock_sent`.
12. If the draft was an order confirmation, go to **Orders** (`/admin/orders`). Confirm the mock order appears with status `created`, a facility assigned, and an estimated total. Open it to see the order timeline (drafted → status change → facility assigned) and its linked conversation.
13. Go to **AI Action Logs** (`/admin/ai-logs`). Confirm multiple rows exist for this conversation/order (`agent_run`, `tool_call` entries for each tool, `llm_complete`, `approve_action`), each expandable via the Input/Output JSON viewers.
14. Back in the conversation, click **Manual Takeover**. Confirm the "Manual takeover is active" notice appears and **Run WhatsApp Agent** becomes disabled.
15. Type a message in **Send Manual Mock Reply** and send it. Confirm it appears immediately as an outbound bubble (no approval step - manual replies bypass the queue by design).
16. Click **Release Takeover**. Confirm **Run WhatsApp Agent** is enabled again.
17. Optional - test the incomplete-info path: send a fresh inbound message like **"I need laundry pickup tomorrow"** without an area, run the agent, confirm it asks a follow-up question instead of creating an order; then reply with an area matching a seeded facility (e.g. the exact facility area from `scripts/seed_mock_data.py`, such as "Dubai Marina") and run the agent again to confirm it now creates the order (multi-turn slot accumulation).
18. Optional - test an out-of-scope message: try the "I want to cancel my order" or "This service is terrible" quick-fill buttons. Confirm the console shows the in-UI hint that the agent has no cancellation/complaint tool, and that running the agent only produces a generic follow-up or escalation - never a fabricated cancellation/refund confirmation.

If any step fails, check `docker compose logs api` and `docker compose logs admin` first.
