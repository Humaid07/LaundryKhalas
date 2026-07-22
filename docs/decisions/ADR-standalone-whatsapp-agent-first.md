# ADR: Standalone WhatsApp Agent Before Classifier/Admin-Dashboard Hardening

## Status

Accepted — 2026-07-18.

## Context

Per `CLAUDE.md` §18, the previously stated roadmap order was: WhatsApp
Agent backend → Admin UI → Classifier Agent → stronger approval/manual
takeover → live WhatsApp readiness → ... Both the WhatsApp Agent backend
and Admin UI were built and verified (see `docs/build-reports/
2026-07-18-admin-ui-build.md`).

The founder/team then explicitly redirected: build a **focused, standalone
WhatsApp Agent** - domain-guarded to laundry/cleaning/LaundryKhalas only,
with its own WhatsApp-Web-style chat UI - as a separate, simpler
deliverable, ahead of the classifier agent and any further admin-dashboard
work. Explicit instructions: do not build the classifier, do not touch the
admin dashboard, do not build SEO/marketing/driver/customer apps, do not
build the payment flow, do not build multi-agent architecture in this task.

This is a deliberate, temporary reordering of the roadmap in `CLAUDE.md`
§18, not a replacement of it.

## Decision

1. Built a new, independent codebase (`apps/whatsapp-agent/` backend +
   `apps/whatsapp-chat/` frontend) rather than extending the main system's
   `app/` or `apps/admin/`. See `docs/architecture/
   standalone-whatsapp-agent.md` for the full rationale (no shared DB
   schema, task explicitly said not to rebuild the order-management
   database).
2. Domain restriction is enforced by two independent layers (deterministic
   keyword guard + system prompt), not one - see `docs/architecture/
   domain-guard.md`.
3. The official Meta WhatsApp Cloud API structure is implemented for real
   (webhook verify, signature check, inbound parsing, outbound send call),
   gated fully behind `WHATSAPP_MODE=live` plus all required Meta env vars
   - never live-tested, never defaulted on. Unofficial WhatsApp automation
   (e.g. Evolution API / WhatsApp-Web-based tools) was explicitly
   considered and explicitly declined for this task - see the "Evolution
   API" discussion in this session's transcript and
   `docs/checklists/live-whatsapp-readiness.md`'s standalone-agent section
   for why: it violates WhatsApp's Terms of Service and risks the number
   being banned, which is unacceptable for a business whose primary
   customer channel is WhatsApp.
4. Unlike the main system's LLM providers (which are stubs that raise
   `NotImplementedError`), this standalone agent's Anthropic/OpenAI
   providers are real, working implementations - gated by
   `Settings.live_llm_ready` (provider selected AND its API key present),
   defaulting to a deterministic mock provider otherwise. This matches the
   task's explicit ask ("real API calls only when key is configured") and
   is a deliberate difference from the main system's current stub-only
   posture, not an inconsistency to reconcile right now.

## Consequences

- Two independent Meta WhatsApp Cloud API integration points now exist in
  this repository (this one, and the main system's stub). A decision is
  needed later on which becomes the actual production integration -
  flagged explicitly in `docs/checklists/live-whatsapp-readiness.md` so it
  isn't discovered by accident.
- Two independent Next.js frontends now exist (`apps/admin/` on port 3000,
  `apps/whatsapp-chat/` on port 3100) and two independent Python backends
  (`app/` on port 8000, `apps/whatsapp-agent/` on port 8100) - all four can
  run side by side in Docker without conflict.
- The classifier agent, admin dashboard, and every other deferred module
  remain untouched and unbuilt, per explicit instruction.
- When work resumes on the main system's roadmap, a decision is needed on
  whether the standalone agent's domain-guard/prompt/knowledge-base
  approach gets folded into the main WhatsApp Operations Agent, replaces
  it, or stays a permanently separate lightweight tool. Not decided here -
  flagged as the natural "next decision" in the build report.

## Related

- `docs/architecture/standalone-whatsapp-agent.md`
- `docs/architecture/whatsapp-cloud-api-integration.md`
- `docs/architecture/domain-guard.md`
- `docs/checklists/live-whatsapp-readiness.md`
- `docs/build-reports/2026-07-18-standalone-whatsapp-agent.md`
