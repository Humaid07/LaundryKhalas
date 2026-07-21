# Live WhatsApp Readiness Checklist

Nothing in this checklist is done in this task. This build is mock-only by
design. Do not enable `WHATSAPP_PROVIDER` other than `mock` or
`META_WHATSAPP_ENABLED=true` until every item below is genuinely true.

**Scope note (added 2026-07-18):** this checklist originally covered only
the main system (`app/`, `apps/admin/`). A second, independent codebase now
also has a Meta WhatsApp Cloud API integration point: the standalone
WhatsApp Agent at `apps/whatsapp-agent/` (`channels/meta_whatsapp.py`,
gated by `WHATSAPP_MODE=live`). See §"Standalone WhatsApp Agent" below for
what's specific to that build - the rest of this checklist still applies to
the main system and is unchanged.

## Meta / WhatsApp Business setup
- [ ] Meta Business Manager access confirmed
- [ ] WhatsApp Business Account (WABA) created and verified
- [ ] Dedicated phone number per market (UAE, Qatar, ...) registered
- [ ] Phone Number ID captured per market
- [ ] WABA ID captured
- [ ] Permanent (non-expiring) access token generated and stored in a secrets
      manager (never in `.env` committed to git)
- [ ] Webhook verification (`hub.verify_token` handshake) implemented and
      tested against `META_WHATSAPP_VERIFY_TOKEN`
- [ ] Message templates submitted and approved for every proactive/outbound
      template message type needed

## Compliance / opt-in-out
- [ ] Opt-in handling implemented and tested
- [ ] Opt-out handling implemented and tested (and respected by the agent -
      no further messages after opt-out)
- [ ] Message status tracking (sent/delivered/read/failed) wired to update
      `Message.status`
- [ ] Rate limit handling (Meta's per-number messaging limits) implemented
      with backoff/retry and alerting

## Operational safety
- [ ] Human takeover verified to actually stop the agent from replying
      (already implemented and tested in mock mode - re-verify against the
      live channel adapter once built)
- [ ] Privacy firewall tests re-run against the live adapter's payloads
      (Meta webhook payload shapes differ from the mock payload shape -
      make sure PII masking still holds)
- [ ] Approval queue verified working end-to-end against live send
- [ ] AIActionLog / OrderEvent logging verified working against live traffic
      volumes (not just single mock test messages)
- [ ] Cost ceilings (per-conversation, per-customer/day, global/day -
      currently structured but not enforced, see
      `app/services/cost_ceiling.py`) actually enforced, not just recorded
- [ ] Real authentication/RBAC in place on all `/api/admin/**` routes
      (current MVP uses a single shared `X-Admin-Api-Key` - not sufficient
      for live launch, see `docs/audits/fresh-project-start-report.md` §12)
- [ ] DB-level order-state transition guard (trigger or constraint), not
      just the Python-level check in `services/orders.py`
- [ ] Founder/team sign-off obtained after reviewing this checklist in full

## Standalone WhatsApp Agent (`apps/whatsapp-agent/`)

Built 2026-07-18 - see `docs/architecture/whatsapp-cloud-api-integration.md`
and `docs/build-reports/2026-07-18-standalone-whatsapp-agent.md`. Already
implemented, mock-mode-tested:

- [x] `GET /webhooks/whatsapp` verify handshake against
      `META_WHATSAPP_VERIFY_TOKEN` (tested)
- [x] `POST /webhooks/whatsapp` inbound message parsing from the real Meta
      payload shape (tested with a synthetic payload matching Meta's schema)
- [x] `X-Hub-Signature-256` verification against `META_WHATSAPP_APP_SECRET`
      (implemented; only exercised in mock mode so far - no real Meta
      signature has been verified against it yet)
- [x] Outbound send call shaped for the real Graph API
      (`POST /{phone_number_id}/messages`) - implemented, **never actually
      called** (`live_whatsapp_ready` gate means this code path only runs
      once `WHATSAPP_MODE=live` and all three Meta env vars are set)
- [x] Live mode is opt-in and requires all of `WHATSAPP_MODE=live` +
      `META_WHATSAPP_ACCESS_TOKEN` + `META_WHATSAPP_PHONE_NUMBER_ID` +
      `META_WHATSAPP_VERIFY_TOKEN` to be present - missing any one keeps it
      on mock, verified by `settings.live_whatsapp_ready`

Still needed before this specific integration can go live (in addition to
every item above, which still applies):

- [ ] A real WABA/phone number/access token to test the send path against
      (nothing above has been tested against Meta's actual API - only the
      payload *shapes* were verified)
- [ ] Message status callback handling (sent/delivered/read/failed) - not
      implemented in the standalone agent; `parse_inbound_webhook` only
      extracts `messages` entries today, ignores `statuses` entries
- [ ] Domain-guard and prompt-injection resistance re-verified against real
      customer phrasing at volume, not just the test-suite examples in
      `docs/checklists/standalone-whatsapp-agent-test-script.md`
- [ ] A decision on whether this standalone agent or the main system's
      `app/channels/meta_whatsapp_stub.py` becomes the actual production
      WhatsApp integration point - right now both exist independently and
      neither is live; running both against the same real phone number
      would double-reply to customers
