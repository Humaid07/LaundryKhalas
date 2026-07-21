# WhatsApp Cloud API Integration (Standalone Agent)

Covers `apps/whatsapp-agent/channels/meta_whatsapp.py` and
`apps/whatsapp-agent/api/webhooks.py` - the official Meta WhatsApp Cloud
API integration for the standalone agent. No unofficial automation,
browser automation, or WhatsApp Web scraping is used or referenced
anywhere in this code path.

## Mode gating

Exactly one property decides whether any live call is possible:
`Settings.live_whatsapp_ready` in `apps/whatsapp-agent/settings.py`:

```python
@property
def live_whatsapp_ready(self) -> bool:
    return self.whatsapp_mode == "live" and bool(
        self.meta_whatsapp_access_token
        and self.meta_whatsapp_phone_number_id
        and self.meta_whatsapp_verify_token
    )
```

`WHATSAPP_MODE=live` alone is not enough - all three Meta env vars must
also be non-empty. Missing any one silently keeps the system on the mock
channel rather than erroring, so a half-configured `.env` fails safe.

## Webhook verification (`GET /webhooks/whatsapp`)

Implements Meta's standard subscribe handshake: echoes `hub.challenge`
back as plain text only if `hub.mode == "subscribe"` and
`hub.verify_token` matches `META_WHATSAPP_VERIFY_TOKEN`; otherwise 403.
This is what you register as the webhook URL in the Meta App Dashboard.

## Signature verification (`POST /webhooks/whatsapp`)

If `META_WHATSAPP_APP_SECRET` is set, every inbound webhook POST must
carry a valid `X-Hub-Signature-256` header - an HMAC-SHA256 of the raw
request body, keyed with the app secret (`MetaWhatsAppChannel.
verify_webhook_signature`). Requests that fail this check are rejected
with 403 before the payload is even parsed. If the app secret is not
configured (e.g. local testing), signature verification is skipped -
acceptable for local/mock use, **not** acceptable once pointed at a real
Meta app (see `docs/checklists/live-whatsapp-readiness.md`).

## Inbound payload parsing

`parse_inbound_webhook()` walks Meta's nested
`entry[].changes[].value.messages[]` shape and extracts only `type ==
"text"` messages as `{phone, text, wa_message_id}` tuples - status
callbacks (`value.statuses[]`, for delivered/read receipts) are present in
real Meta payloads but not yet handled (tracked as a gap in the readiness
checklist, not silently dropped-and-forgotten).

## Outbound send

`MetaWhatsAppChannel.send_text()` POSTs to
`https://graph.facebook.com/v20.0/{phone_number_id}/messages` with a
standard text-message payload, bearer-token authenticated from
`META_WHATSAPP_ACCESS_TOKEN`. This method exists and is unit-testable, but
is **never actually invoked** unless `live_whatsapp_ready` is true - see
`api/webhooks.py`, which branches to `MockWhatsAppChannel` otherwise.

## What has and hasn't been verified

Verified (via `tests/test_webhook.py` and manual testing during this
build): the verify-token handshake, signature-rejection on a bad/missing
signature, and payload parsing against a synthetic payload matching Meta's
documented schema.

**Not verified**: nothing here has been tested against Meta's actual API -
there is no real WABA, access token, or phone number in this environment.
The send path, real signature verification against a real app secret, and
real-world payload edge cases (e.g. media messages, status callbacks) are
all unverified. Do not treat "the code exists" as "this is live-ready" -
see the standalone-agent section of `docs/checklists/
live-whatsapp-readiness.md` for the explicit gap list.
