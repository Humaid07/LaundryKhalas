# Evolution API WhatsApp Integration — Architecture

> **Current** WhatsApp provider for testing (self-hosted Evolution API gateway).
> Selected by `WHATSAPP_MODE=evolution`. Mock stays the default; Meta is a future
> placeholder. Related: [[project-whatsapp-provider-modes]] (memory),
> [[whatsapp-agent-dashboard-inbox]], [[supabase-dev-database]],
> [[privacy-firewall]].

## Flow

```
WhatsApp user ──▶ Evolution API server ──(webhook: messages.upsert)──▶ FastAPI
                        ▲                                                  │
                        │                                          store in Supabase
                        └──(POST /message/sendText)────────────────  inbox (dashboard)
                            (human-approved operator reply)                │
                                                                    operator replies
```

The dashboard never talks to WhatsApp or Evolution — only to FastAPI. FastAPI
picks the provider from `WHATSAPP_MODE`.

## Components

- `channels/evolution_whatsapp.py`
  - `EvolutionWhatsAppChannel(base_url, api_key, instance)` — `.send_text(to_phone,
    text)` → `POST {base}/message/sendText/{instance}` with header `apikey`;
    `.instance_status()`; `.from_settings()`.
  - `parse_evolution_webhook(payload)` — flattens a `messages.upsert` event into
    `[{phone, text, name, wa_message_id}]`; ignores `fromMe`, groups,
    `status@broadcast`, and non-text/other events. Handles plain / extended /
    caption text shapes.
- `api/evolution_webhooks.py` — `POST /webhooks/evolution` (inbound).
- `db/repositories/customers_repo.py` — `get_or_create_by_phone` (real inbound
  sender). `conversations_repo` gains `get_or_create_for_customer`,
  `register_inbound`, `set_flagged`, `get_customer_phone`. `flags_repo.create`.
- `api/conversations.py` — outbound: the inbox `human-message` endpoint sends the
  operator's reply live via Evolution when ready.

## Inbound behaviour (`POST /webhooks/evolution`)

For each inbound 1:1 text message:
1. upsert the customer (`phone_hash` lookup; stores `phone_e164` backend-only +
   `masked_phone`) and get/create a `bot` conversation,
2. store the customer message + bump `last_message`/`unread_count`,
3. run the agent (`handle_message(..., db=None)`) to draft a reply and detect an
   escalation (`services.escalation.detect_escalation`),
4. **on escalation/handoff** → set the conversation `human_needed` with
   priority/team, and create an `agent_flags` row (draft stored as
   `suggested_reply`). Category→(flag_type, priority, team) map lives in the
   webhook module (refund→urgent/Finance, damaged→high/Facility, b2b→medium/
   Sales, …).
5. **happy path** → held by default. Only if `EVOLUTION_AUTO_REPLY=true` AND
   `evolution_live_ready` is the draft auto-sent via Evolution.

In local SQLite mode the webhook returns `{stored:false}` (the inbox is a
Supabase feature) — it never fails delivery.

## Outbound behaviour

`POST /api/conversations/{id}/human-message` stores the operator's reply and,
when `settings.evolution_live_ready`, looks up the customer's real `phone_e164`
(backend-only) and sends via `EvolutionWhatsAppChannel`. The response carries
`send_status` (`sent` | `stored` | `send_failed`). In mock mode it is only
stored — nothing is sent.

## Approval / safety model (MVP)

- The **agent never auto-sends** live WhatsApp by default. Escalations are always
  held for a human; happy-path replies are held unless `EVOLUTION_AUTO_REPLY` is
  explicitly enabled.
- The **sanctioned live-send path is a human operator's manual reply** (via the
  inbox), consistent with CLAUDE.md §6/§8.
- Gated end-to-end by `evolution_live_ready` (evolution mode + all `EVOLUTION_*`
  vars). With `WHATSAPP_MODE=mock`, nothing is ever sent.

## Privacy

- Full number stored only in `customers.phone_e164` (backend-only, used to send)
  + `phone_hash`; every read API returns `masked_phone` only. Verified: inbound
  responses never contain the raw number.

## Config

`WHATSAPP_MODE=evolution`, `EVOLUTION_API_BASE_URL`, `EVOLUTION_API_KEY`,
`EVOLUTION_INSTANCE_NAME`, `EVOLUTION_AUTO_REPLY` (default false). Point the
Evolution instance's webhook (event `messages.upsert`) at
`{backend}/webhooks/evolution`.

## Not built

- Evolution media (image/audio/document) send — text only for now (captions are
  parsed inbound).
- Delivery/read status callbacks.
- Per-instance webhook signature verification (Evolution local/dev).
