# Build Report — Agent & Dashboard Inventory

**Date:** 2026-08-05
**Module:** Whole system — AI agents ↔ dashboards
**Type:** Inventory / architecture audit (no new application code was written; this is a code-verified map of what already exists)

> Honesty note (CLAUDE.md §20): This report documents the **current** state of
> the codebase as read from source on 2026-08-05. It builds nothing new. Where the
> code diverges from older docs or `CLAUDE.md` language, the code is treated as the
> source of truth and the divergence is called out.

---

## 1. Objective
Produce a single, honest answer to: *"What agents have we built, what does each
actually do, and how do they coordinate with the dashboards?"* — verified against
the real code, distinguishing **live-wired** from **mock/placeholder** from
**deferred/not-built**.

## 2. Method
Two parallel read-only code sweeps: (a) every AI/agent module across
`apps/whatsapp-agent/`, `seo_agents/`, `laundry_class/`, and the archived root
`app/`; (b) every frontend dashboard under `apps/` and the exact API contract each
uses. Findings below are from source, nav/section configs, and `.env` defaults —
not from memory or docs.

---

## 3. System shape (one paragraph)
**One canonical backend** — `apps/whatsapp-agent/` (FastAPI + Supabase/asyncpg +
Evolution WhatsApp + Claude tool-use), port **:8100** — serves **three thin-client
dashboards**. No frontend touches Supabase directly; all data flows through the
backend's `/api/*`. Default posture is **mock-first**: `llm_provider = "mock"` and
`WHATSAPP_AGENT_MODE = paused`. The Evolution webhook and Supabase persistence are
**real code paths gated by config** — flip the flags and they run live.

---

## 4. Agent inventory

### 4.1 🟢 WhatsApp Operations Agent — the real, live-capable agent
The one genuinely built-and-wired agent. Dual-path: uses real Claude only when
`live_llm_ready` (provider `anthropic` + `ANTHROPIC_ENABLED` + API key), otherwise
falls through to the deterministic mock provider.

| Component | Path | Responsibility | Status |
|---|---|---|---|
| Orchestrator | `agents/whatsapp_agent/agent.py` | Per-turn pipeline: domain guard → escalation handoff (no LLM) → intent → deterministic order flow → LLM reply text | Live (mock by default) |
| LLM service + providers | `llm/service.py`, `llm/providers/{anthropic,mock,openai}.py` | Provider selection, agentic tool loop, prompt caching, cost/token accounting | Anthropic live; Mock default; OpenAI optional |
| Read-only tools | `agents/whatsapp_agent/llm_tools.py` | The only Claude→data bridge: `lookup_item_price`, `list_service_categories`, `estimate_turnaround`, `check_service_area`, facility reads | Live, **read-only** |
| Booking write-tools | `agents/whatsapp_agent/booking_tools.py` | Schema-validated actions scoped to one order: save name/service/items/date/time/address, `confirm_order`, `negotiate_order_price`, `quote_express`, `create_complaint`, `route_to_specialist`, `request_human_support` | Live, gated behind live + tool-use |
| Facility tools | `agents/whatsapp_agent/facility_tools.py` | Read-only facility lookup (eligible facilities, hours, services) | Live, Supabase-gated |

**Model (code default):** `claude-opus-4-8` when live; `mock-1` otherwise.

**Load-bearing safety design:**
- Booking is a **deterministic FSM** (`services/booking_flow.py`). The LLM **cannot**
  skip states, set prices, or confirm an order — it only produces reply text and
  calls narrow validated tools.
- High-risk topics (refund / complaint / damage / abuse / threat) are intercepted
  **before** the LLM by `services/escalation.py` + `services/domain_guard.py` and
  routed to humans.

### 4.2 🟢 Deterministic decision engines (live, no LLM)
Rule-based, config-driven "brains" that make the agent safe. Not LLM agents, but
they do the classifying/routing the roadmap "classifier" was meant to:
`service_resolution` (valid/ambiguous/unsupported service), `abuse_classification`
(dissatisfaction vs insult vs threat → AI-pause takeover), `specialty_routing`
(villa/wedding/bespoke), `negotiation` (the only sanctioned path off baseline
price), `facility_routing` (auto-assigns a partner on confirm → feeds Facility
Dashboard), `persona_assignment`, `customer_memory`, `post_confirmation`,
`reply_style` (no-dash normaliser).

### 4.3 🟡 Laundry Class agent (LangGraph) — real graph, LLM off by default
`laundry_class/` — a full **alternative** agent as a real LangGraph `StateGraph`
(`START → agent_turn → handoff_notify → END`, per-phone SQLite checkpoint memory).
Structurally live, but the responder is a **deterministic composer by default**;
`build_chat_model()` only returns a live `ChatAnthropic` when explicitly enabled.
Secondary / experimental — parallel to 4.1, not in the main WhatsApp path.

### 4.4 🟡 SEO Agent fleet — 16 agents, mock by design
`seo_agents/catalog.py` — SEO-01…SEO-16 (Competitor Monitor, News/Trend, GSC
Monitor, Indexing, Content Research, Blog+Schema Draft, Topical Authority, Internal
Linking, Backlinks, Duplicate Content, Money-Page Opt, Local/Area Page, Content
Decay, AI-Search Visibility, GCC Expansion, SEO Reporting). **No LLM, no web calls,
`cost=0`, status "Staged."** Each turns a deterministic mock source into
dashboard findings; every recommendation becomes a human-approval task; all
publish/outreach/submit actions are hard-forbidden. Placeholder by design.

### 4.5 🔴 Classifier Agent — DEFERRED / archived (not built)
The roadmap "Classifier Agent" (pre-agent intent/sentiment/urgency labeller) **does
not exist in code.** The legacy root `app/` — which once held
`app/agents/classifier/` — was archived empty in commit `a1a8268`. Only
`docs/architecture/classifier-agent.md` still describes it. **Do not confuse** it
with the live deterministic classifiers in §4.2, which are message-level engines,
not the roadmap agent.

---

## 5. Dashboards & how they coordinate with the agent

**Runtime flow:** inbound WhatsApp → `POST /webhooks/evolution` (allow-list +
`wa_message_id` dedupe) → PII-masked, debounced/aggregated → stored in Supabase →
agent routes (escalation / booking / reply) → surfaces appear in dashboards via
`/api/*`.

### 5.1 `apps/admin/` — internal operations command center (:3005)
Large 11-section dashboard; **only part is live-wired** to the agent.

| Admin surface | Wired? | Agent connection / endpoints |
|---|---|---|
| Operations → Customer Facing | 🟢 Live | Live WhatsApp inbox + agent **flags** (each flag carries `suggested_reply` + `suggested_action`). `NEXT_PUBLIC_USE_LIVE_WHATSAPP_INBOX`-gated. `/api/conversations*`, `/api/flags*` |
| Operations → Human Intervention | 🟢 Live | Abuse/refund/takeover queue: `/api/human-intervention/{queue,metrics,claim,resolve,release-to-ai}` |
| Operations → Facility Facing | 🟢 Live | Facility-raised issues, PII-free: `/api/internal/facility-issues*` |
| Orders | 🟢 Live | Agent-created orders, polled 15s: `/api/orders/{search,metrics/summary,{id}/events,photos,status}` |
| Facilities / Pricing / Taxonomy health | 🟢 Live | Catalogue the agent reads for prices; `/api/service-taxonomy/health` |
| Overview, Sales, SEO Agents, Marketing, Finance & Compliance, Dev & Automation, Reports | 🔴 Mock | Static data; sidebar KPI numbers are hardcoded strings |

### 5.2 `apps/facility-dashboard/` — partner facilities (:3010)
**Fully wired, no mock layer, PII-firewalled** (no customer phone/email/full
address). Facilities receive agent-assigned orders, upload intake/pre-dispatch
photos, raise issues (→ admin Facility Facing), manage drivers/assignments, view
read-only ratings + finance/payouts. `/api/facility/*`.

### 5.3 `apps/whatsapp-chat/` — agent test console (:3100)
Internal harness to talk to the agent without live WhatsApp. Posts to
`/api/test-chat/message`; ModeBanner/DebugPanel surface the "Live WhatsApp: Off /
Live LLM: Off" posture. Conversations stored in `localStorage`.

---

## 6. What is mock-only
- Admin **Overview** + entire **Sales / Partner Acquisition / SEO Agents /
  Marketing / Finance & Compliance / Dev & Automation / Reports** trees, and all
  hardcoded sidebar KPI numbers.
- **SEO fleet** (§4.4) — 16 staged agents, no LLM.
- **Laundry Class** LLM (§4.3) — deterministic composer unless explicitly enabled.
- Default LLM provider = mock; WhatsApp agent = paused.

## 7. What is live (config-gated)
- WhatsApp Operations Agent (§4.1) + Anthropic provider + read/write tools.
- Admin Operations (Customer Facing, Human Intervention, Facility Facing), Orders,
  Facilities, Pricing; whole Facility Dashboard; whatsapp-chat console.
- Evolution inbound webhook + Supabase persistence.

## 8. What is deferred / not built
- **Classifier Agent** (§4.5) — archived, docs-only.
- Live SEO sources (GSC etc.), live Meta WhatsApp, live Stripe, live SEO/marketing
  LLM agents — all per roadmap.

## 9. Honest gaps vs CLAUDE.md
1. **No single "approve every draft" queue.** `CLAUDE.md` §8 describes an
   approval-request-per-reply flow. The live design instead surfaces agent
   suggestions via **flags** (`suggested_reply`) + **manual takeover**, not a
   dedicated draft-approval route. (`CLAUDE.md` predates the Evolution/Supabase
   pivot.)
2. **No live AI-action-log view.** §10/§11 imply an agent-activity log surface;
   Dev & Automation → Logs/LLM-Cost/Agent-Health are all placeholder. Tool calls
   *are* logged server-side, but there is no wired dashboard view.
3. **Model drift note.** Code default is `claude-opus-4-8`; an earlier decision
   set the WhatsApp runtime to Haiku 4.5. Confirm which is actually intended for
   the live runtime before any live billing.

## 10. Security / privacy notes
- PII masking on inbound (`services.privacy`) before storage; facility-facing
  surfaces are PII-free by construction.
- Escalation/abuse topics never reach the LLM.
- All booking writes go through schema-validated tools scoped to one order — no
  free-form SQL from the model.

## 11. Cost / LLM usage notes
- Default = zero LLM cost (mock provider). SEO fleet = `cost=0` by design.
- Live cost only when `live_llm_ready`; `llm/costs.py` accounts tokens.

## 12. How to verify manually
- Backend: `apps/whatsapp-agent/` on :8100 (venv). Test console: `apps/whatsapp-chat`
  on :3100 → send a message → watch it hit `/api/test-chat/message`.
- Admin live inbox: `apps/admin` with `NEXT_PUBLIC_USE_LIVE_WHATSAPP_INBOX=true`
  pointed at :8100 → Operations → Customer Facing.
- Confirm posture: `GET /api/settings/status` should report mock LLM / paused agent.

## 13. Next recommended steps
1. **Decide the runtime model** (Opus 4.8 vs Haiku 4.5) and make code + docs agree.
2. **Reconcile CLAUDE.md §8** with the flags/takeover reality, or build the
   explicit draft-approval queue if that's still wanted.
3. **Wire one live AI-action-log view** in admin (the server already logs tool
   calls) — closes the biggest observability gap.
4. If the roadmap still wants it, **scope the Classifier Agent** as a fresh module
   in `apps/whatsapp-agent/` (the old `app/` version is gone).

---

## Related docs
- `docs/architecture/canonical-backend-runtime.md`
- `docs/architecture/evolution-whatsapp-integration.md`
- `docs/architecture/classifier-agent.md` (describes the deferred agent)
- `docs/architecture/facility-dashboard.md`, `facility-privacy-firewall.md`
- `docs/build-reports/2026-08-04-whatsapp-historical-replay-harness.md`
