# Build Report — Evolution API WhatsApp Adapter

**Date:** 2026-07-21
**Area:** `apps/whatsapp-agent` (channels, webhook, repos, inbox outbound)

## Objective

Build the Evolution API adapter so real WhatsApp messages flow into the Supabase
inbox and human-approved operator replies go back out — the current WhatsApp
provider (`WHATSAPP_MODE=evolution`), mock-by-default.

## What was built

- **Send + parse** (`channels/evolution_whatsapp.py`): `EvolutionWhatsAppChannel`
  (`send_text` → `POST /message/sendText/{instance}` with `apikey`;
  `instance_status`; `from_settings`) and `parse_evolution_webhook` (flattens
  `messages.upsert`, ignores fromMe/groups/status/non-text).
- **Inbound webhook** (`api/evolution_webhooks.py`, `POST /webhooks/evolution`):
  upsert customer + conversation, store the message, draft a reply, and on an
  escalation set the conversation Human Needed + create a flag with the draft as
  the suggested reply. Happy-path drafts are held unless `EVOLUTION_AUTO_REPLY`.
- **Outbound** (`api/conversations.py`): the inbox `human-message` endpoint sends
  the operator's reply live via Evolution when `evolution_live_ready`; response
  includes `send_status`.
- **Repos**: new `customers_repo.get_or_create_by_phone`; `conversations_repo`
  gains `get_or_create_for_customer`, `register_inbound`, `set_flagged`,
  `get_customer_phone`; `flags_repo.create`.
- **Privacy** (`services/privacy.py`): `mask_phone`, `hash_phone`.
- **Settings**: `evolution_live_ready`, `evolution_auto_reply` (default false).
- **main.py**: registered the Evolution webhook router.
- **.env.example**: `EVOLUTION_AUTO_REPLY` + webhook-URL guidance.

## Files created / modified

Created: `channels/evolution_whatsapp.py`, `api/evolution_webhooks.py`,
`db/repositories/customers_repo.py`, `tests/test_evolution_channel.py`,
`docs/architecture/evolution-whatsapp-integration.md`, this report.
Modified: `api/conversations.py`, `db/repositories/{conversations_repo,flags_repo}.py`,
`services/privacy.py`, `settings.py`, `main.py`, `.env.example`.

## Endpoints

`POST /webhooks/evolution` (inbound). Outbound reuses
`POST /api/conversations/{id}/human-message` (now with live Evolution send +
`send_status`).

## Safety / approval (MVP)

Agent never auto-sends by default; escalations always held for a human;
happy-path auto-send only if `EVOLUTION_AUTO_REPLY=true`. The sanctioned live-send
path is a human operator's manual reply. Everything gated by `evolution_live_ready`
— with `WHATSAPP_MODE=mock`, nothing is sent.

## Privacy

Full number only in `customers.phone_e164` (backend-only) + `phone_hash`; read
APIs return `masked_phone` only. Verified inbound responses never leak the raw
number.

## Tests / checks

- `pytest` **174 passed** (10 new in `tests/test_evolution_channel.py`: parser
  variants, fromMe/group/status filtering, `send_text` against a fake httpx
  client, webhook graceful in SQLite mode). ruff clean.
- **Live end-to-end** against the running Evolution server + dev/test Supabase
  (backend in supabase DB + mock WhatsApp): POSTed two synthetic inbound events →
  a happy-path message and a refund message. Result: conversation created with
  **masked phone (no raw-number leak)**, both messages stored, refund →
  `human_needed` / `urgent` / "Customer Facing / Finance" + a `refund_request`
  flag. Human reply in mock mode returned `send_status: stored` (not sent).
  Synthetic rows cleaned up; seed intact.

## Known limitations

- No media send (text only; inbound captions parsed), no delivery/read callbacks,
  no Evolution webhook signature verification (dev/local).
- Inbox is Supabase-only; in sqlite mode the webhook acks without storing.
- `WHATSAPP_MODE` is still `mock` in the local `.env` — flipping to `evolution`
  (and pointing Evolution's webhook at `/webhooks/evolution`) turns on live
  send/receive. Going live is a deliberate, approval-gated switch.

## Next step

Configure the Evolution instance's webhook → `{backend}/webhooks/evolution`, set
`WHATSAPP_MODE=evolution`, and do a supervised live round-trip from a test phone;
then decide on `EVOLUTION_AUTO_REPLY` for happy-path automation.
