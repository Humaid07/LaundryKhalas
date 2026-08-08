# Inbound-Image Vision for the WhatsApp Agent — Design

- **Date:** 2026-08-07
- **Status:** Approved (pending written-spec review)
- **Scope:** `apps/whatsapp-agent` — Evolution webhook, channel, llm service, new vision service
- **Changes live agent behavior** (customer-facing). Behind a config flag.

## Problem

Customers send photos (e.g. a loafer for shoe care / restoration). Today the
inbound pipeline classifies the message as `MediaKind.IMAGE`
(`services/media_classification.py`) but the webhook only special-cases `audio`.
An image therefore falls through to the normal booking turn **with empty text** —
the bytes are never downloaded and never sent to Claude's vision API, and (unlike
voice notes) there is no graceful fallback. The agent effectively receives a
blank message and cannot assess the item.

## Goal

When a customer sends a photo, the agent **downloads it, stores it, and uses
Claude vision to describe the item and its visible condition** (e.g. "leather
loafer, scuffed toe, worn sole"), then continues the normal booking turn so the
photo-quote / facility flow can proceed. The image is stored and visible to the
facility on the order.

## Decisions (from brainstorming)

1. **Describe-only.** Vision identifies the item + visible condition. It NEVER
   invents a price, turnaround, or repairability verdict (CLAUDE.md §5/§6).
   Pricing stays in the grounded facility-quote flow.
2. **Every image + store it.** Run vision on every inbound photo; persist bytes
   via `media_storage` (R2/local), linked to the conversation and, once it
   exists, the order — so the facility can see it (`order_photos`).
3. **Flag on by default** (`WHATSAPP_IMAGE_VISION_ENABLED=true`) whenever the
   live Anthropic provider is active; the mock provider returns a canned
   description so the hermetic test suite makes no live call.

## Non-goals (YAGNI)

- Damage severity / repairability judgment.
- Price/turnaround from vision.
- Video / document / sticker vision (still classified, still text-fallback).
- Multi-image batching; re-running vision on an already-described image.

## Design

### Flow — new `image` branch in `api/evolution_webhooks.py`

Placed alongside the existing `audio` branch (`~line 1052`), BEFORE the model
turn:

```
media_kind == "image":
  1. bytes, mime = await channel.download_media(raw_message)   # Evolution REST
  2. stored = await media_storage.store(...)                   # R2/local
     link media -> conversation (+ order once present)         # order_context / order_photos
  3. vision = await image_vision.describe_image(bytes, mime)   # Sonnet 5, describe-only
  4. inject as the turn's user text:
        "[Customer sent a photo: <vision.summary>]" (+ caption if any)
  5. fall through to the normal booking turn with that text
  on ANY failure (download/vision): send ONE graceful ack (parity with
  services/voice_fallback), store the image if we got it, never raise.
```

The injected text is explicitly marked as a photo description (observation), not
a customer claim, so the agent grounds pricing through the normal flow.

### Components

| File | Role |
|------|------|
| `channels/evolution_whatsapp.py` | **add** `download_media(message) -> (bytes, mime)` — one `POST /chat/getBase64FromMediaMessage/{instance}` call with the message key + apikey; decodes base64. Defensive: raises a typed error the webhook catches. |
| `services/image_vision.py` | **new** — `describe_image(bytes, mime) -> VisionResult | None`. Resizes / size-caps, calls the llm vision path with a describe-only prompt, parses a short structured result (`item`, `material?`, `visible_condition`, `summary`, `raw`). Returns `None` on any failure. Pure of web I/O beyond the llm call. |
| `llm/service.py`, `llm/providers/anthropic.py` | **add** `describe_image(image_b64, mime, prompt) -> str`: sends ONE vision content-block (`{"type":"image","source":{"type":"base64",...}}`) to Sonnet 5. Mock provider returns a canned description (hermetic). Kept separate from the booking message history — a focused single-shot call. |
| `api/evolution_webhooks.py` | **add** the `image` branch + fallback ack. |
| storage/link | reuse `media_storage` (bytes) + `order_context` media→order link + `order_photos` (facility visibility). Pre-order photos attach to the order on creation. |
| `settings.py` | **add** `whatsapp_image_vision_enabled: bool = True`. |

### Safety / privacy (CLAUDE.md §5–7)

- Describe-only system prompt; forbids price/turnaround/repairability.
- Cost guard: cap max dimension + byte ceiling; exactly one vision call/image.
- Mock provider → canned description; the hermetic suite never calls live.
- Stored bytes are the customer's own item photo; facility visibility via the
  existing PII-safe `order_photos` surface. No new PII exposure.

### Error handling

- Download fails → graceful ack ("Thanks for the photo — I've noted it for our
  specialist"), continue; never crash the turn.
- Vision fails / flag off / mock with no canned → treat like audio-style
  fallback: acknowledge the photo and ask for a one-line description.
- Oversized/uparseable image → same fallback.

## Testing (TDD, written first)

- `services/image_vision`: mock llm → returns description; prompt is
  describe-only (asserts no price wording); llm error → `None`.
- `channels.download_media`: correct Evolution endpoint + payload; base64 decode;
  error path raises typed error.
- webhook `image` branch: imageMessage → download+store+vision+injected text →
  normal turn runs with that text; download/vision failure → fallback ack, no
  raise; flag off → fallback.
- provider `describe_image`: vision content-block shape; mock canned path.

## Files touched

- `apps/whatsapp-agent/channels/evolution_whatsapp.py`
- `apps/whatsapp-agent/services/image_vision.py` (new)
- `apps/whatsapp-agent/llm/service.py`, `llm/providers/anthropic.py`
- `apps/whatsapp-agent/api/evolution_webhooks.py`
- `apps/whatsapp-agent/settings.py`
- new test module(s) under `tests/`

## Rollout

Flag `WHATSAPP_IMAGE_VISION_ENABLED` defaults true (live Anthropic only; mock →
canned). No migration (reuses `order_photos` 000032, already applied). Reversible
by flipping the flag.
