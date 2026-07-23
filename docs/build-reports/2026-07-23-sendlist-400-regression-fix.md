# Build Report — Evolution `sendList` 400 regression fix

**Date:** 2026-07-23
**Module:** WhatsApp Operations Agent → Evolution channel

## 1. Task objective
The live agent replied correctly but every service/slot/instruction prompt logged
`evolution_interactive_failed … 400 Bad Request` on `POST /message/sendList` before
falling back to numbered text — adding a ~5s dead round-trip per prompt. Fix the
regression.

## 2. Root cause
Reproducing the exact payload the code sends returned:

```json
{"status":400,"error":"Bad Request","response":{"message":["TypeError: this.isZero is not a function"]}}
```

`this.isZero is not a function` is an **internal Baileys library error** raised while
**encoding** a WhatsApp `listMessage` — it is NOT a payload problem. No row/description/
section tweak avoids it. It appeared because the shipping **WhatsApp Web protocol
version** on this instance (`whatsappWebVersion 2.3000.1043697885`) is incompatible with
this Evolution 2.3.7 + Baileys build's list-message encoder. The earlier fix (recorded in
memory) addressed a *different* 400 — the empty-row-description validation error — which is
still correctly guarded in `send_list`. WhatsApp's protocol later shifted and broke list
encoding wholesale at the library level, which reads as a "regression".

Because native lists cannot encode on this build, the correct fix is to **stop attempting
them** and send the reliable numbered-text menu directly — identical customer content,
no failed round-trip, no error logs, ~4s faster per prompt.

## 3. What was built / changed
- `settings.py` — `evolution_use_interactive` default flipped **`True` → `False`**, with a
  comment documenting the `isZero` library incompatibility and how to re-trial
  (`EVOLUTION_USE_INTERACTIVE=true`) on a future build/WhatsApp-Web version where
  `sendList` encodes successfully. Native buttons were already `False`.

No code paths were removed: `send_list`/`send_buttons` and the numbered-text fallback are
unchanged. When the setting is on and a send still fails, the existing fallback path
remains. Interactive **inbound** parsing (`listResponseMessage`/`buttonsResponseMessage`)
is untouched, so a build with working lists still resolves taps.

## 4. Files modified
- `apps/whatsapp-agent/settings.py`

## 5. Files created
- `docs/build-reports/2026-07-23-sendlist-400-regression-fix.md` (this file)

## 6. API / DB / UI
- None. No endpoint, schema, or dashboard change.

## 7. Agent behaviour change
- Service/slot/instruction prompts are now sent as **numbered text by default** (customer
  replies "1", "2", …). Previously each attempted a native list, 400'd, then fell back.

## 8. Mock vs live
- Change is live-path (Evolution). No live LLM/Stripe involved. Agent mode stays `test`.

## 9. Tests run
- `pytest tests/test_service_selection_interactive.py tests/test_booking_flow.py tests/test_evolution_channel.py tests/test_whatsapp_config.py -q`
- **Result: 62 passed.** (These exercise the payload builder + FSM directly and do not
  depend on the setting default, so they stayed green.)

## 10. Manual verification
- Injected a booking from allow-listed `+971543216640` via the real webhook after restart.
- Backend log: `booking_step … state=waiting_for_service` → `evolution_numbered_sent kind=list`.
- **No `sendList` call, no `evolution_interactive_failed`, no 400.** Request completed in
  ~2s (was ~6s). Outbound delivery to the number confirmed separately (Evolution
  `sendText` → `status: PENDING`).

## 11. Known limitations
- Native tappable lists remain unavailable until Evolution/Baileys ships a list encoder
  compatible with the current WhatsApp Web protocol. Re-enable per-env to re-test then.
- The connected instance (`+91 93725 22055`, "Humaid") is a personal WhatsApp; unrelated
  personal traffic flows through it. A dedicated number is recommended for real testing.

## 12. Security / privacy
- No PII exposed; phone numbers remain masked in logs. No secrets touched.

## 13. Next recommended step
- Optional: commit (`settings.py` + this report) to `main` when you're ready.
- Optional: advance an injected booking through the full flow to confirm a completed order
  lands in the dashboard.
