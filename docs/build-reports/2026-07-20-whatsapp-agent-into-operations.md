# Build Report — WhatsApp Agent wired into Operations

**Date:** 2026-07-20
**Modules:** `apps/admin` (dashboard, :3000) ↔ `apps/whatsapp-agent` (backend, :8100)
**Status:** ✅ Wired, typechecked, built, browser-verified end-to-end. Mock-only.

---

## 1. Objective
Make the dashboard's **Operations → WhatsApp Agent** tab real: replace the static
mock chat preview with a live console that talks to the existing standalone
WhatsApp Agent backend (an existing *local mock* service — no live third-party
calls), while honoring the MVP rules (every agent reply requires approval;
interactive actions attach to the specific message).

## 2. What was built
A **Live Agent Console** in the Operations tab that:
- Checks backend health on mount and shows an **Agent online / offline** chip
  (with a copy-paste start command + retry when offline).
- Lets you send a **customer message** (free text or presets) → calls the real
  agent → shows the reply as a **draft "awaiting approval"** with its domain
  classification (`in_domain` / `out_of_domain`) and provider.
- **Approve & send / Edit / Reject / Write manual reply (human takeover)** — the
  approval gate. Only approved replies enter the thread.
- Renders the agent's **interactive action buttons attached to its message**;
  tapping one sends it back as the next turn (`action_id`) — matching the
  standing "actions-attach-to-message" rule.
- Shows an **Agent status** panel (backend URL, LLM provider mock/live, WhatsApp
  mode mock/live, database) from `GET /api/settings/status`.

## 3. Files created
- `apps/admin/lib/dashboard/whatsapp-agent-api.ts` — typed client for the agent
  backend (`health`, `settingsStatus`, `sendMessage`); base URL from
  `NEXT_PUBLIC_WHATSAPP_AGENT_API_URL` (default `http://localhost:8100`).
- `apps/admin/components/dashboard/WhatsAppAgentConsole.tsx` — the console.

## 4. Files modified
- `apps/admin/app/(dashboard)/operations/page.tsx` — WhatsApp tab now renders
  `<WhatsAppAgentConsole/>`; removed the static sample thread + mock list; cleaned imports.
- `apps/admin/.env.example` — documented `NEXT_PUBLIC_WHATSAPP_AGENT_API_URL`.
- `apps/whatsapp-agent/settings.py`, `.env`, `.env.example` — added
  `http://localhost:3000` + `http://127.0.0.1:3000` to `ALLOWED_ORIGINS` (CORS)
  so the dashboard's browser calls to :8100 are allowed.

## 5. API endpoints used (existing, unchanged)
- `POST /api/test-chat/message` — send message → `{ conversation_id, agent_reply, domain, mode, provider, actions[] }`
- `GET /api/settings/status` · `GET /health`

## 6. What is mock / what is live
Everything is **mock**: `LLM_PROVIDER=mock`, `WHATSAPP_MODE=mock`, SQLite. The
console talks to a local backend only — no WhatsApp/LLM/third-party calls. The
agent status panel surfaces `mock` for both LLM and WhatsApp.

## 7. Approval-gate note (honest)
The backend's `/api/test-chat/message` stores its reply immediately (it has no
server-side approval state). The console therefore enforces the approval gate at
the **UI layer**: the drafted reply is held and only rendered as "sent" after the
operator approves (or edits/takes over). Persisting an approval workflow
server-side is deferred.

## 8. Tests run & results
- `tsc --noEmit`: **PASS** (0 errors).
- `npm run build`: **PASS** — `/operations` compiles as a client route (7.4 kB).
- **CORS preflight** from `Origin: http://localhost:3000` → `access-control-allow-origin: http://localhost:3000` ✅
- **Playwright end-to-end** (fresh dev server + live backend): "Agent online"
  chip appears; in-domain message → draft → **Approve & send** → reply enters
  thread; out-of-domain "weather" message → `out_of_domain` refusal draft.
  **0 console errors.** Screenshot captured.

## 9. Known limitations / deferred
- No server-side approval persistence (UI-gated, see §7).
- Console is a single live "test customer" session; it doesn't list historical
  conversations (backend has no list-conversations endpoint) — the other
  Operations sub-tabs remain mock.
- Global filters/search still presentational.

## 10. How to run & verify
```bash
# Backend
cd "D:/Laundry Khalas App/apps/whatsapp-agent"
.venv/Scripts/python.exe -m uvicorn main:app --port 8100
# Dashboard
cd "D:/Laundry Khalas App/apps/admin" && npm run dev   # :3000
```
Open `http://localhost:3000/operations` → WhatsApp Agent tab → send a message →
approve the draft. If the chip shows "Agent offline", start the backend and click Retry.

## 11. Next recommended step
Add a server-side approval/outbound record so approvals persist, and make the
Operations global filters re-slice data. Then consider a "list conversations"
endpoint so the console can show real conversation history.
