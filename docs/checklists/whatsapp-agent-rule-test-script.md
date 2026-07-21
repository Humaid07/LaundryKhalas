# WhatsApp Agent — Rule Test Script

Manual + automated verification for the config-driven rule layer
([[whatsapp-agent-rules]]). All checks are **mock-mode**.

## Automated tests

```bash
cd "apps/whatsapp-agent"
.venv/Scripts/python.exe -m pytest -q
```

Expected: **117 passed** (1 teardown error on Windows only — a SQLite file
lock while deleting the temp test DB; not a test failure).

Rule coverage lives in `tests/test_agent_rules.py` (+ existing
`test_quick_actions.py`, `test_chat.py`, `test_domain_guard.py`, `test_tools.py`):

| # | Rule | Test |
|---|---|---|
| 1 | Greeting → welcome + actions | `test_greeting_returns_configured_welcome_and_menu` |
| 2 | Book Pickup → service options | `test_book_pickup_offers_only_configured_services` |
| 3 | Track Order → asks for order ID | `test_track_order_asks_for_order_id_in_demo_mode` |
| 4 | Cancel Order → asks ID, never cancels | `test_cancel_order_asks_for_id_and_never_cancels` |
| 5 | Out-of-domain refused (configured msg, no LLM) | `test_out_of_domain_uses_configured_refusal` |
| 6 | Unpriced service does not invent price | `test_unpriced_service_does_not_invent_a_price` |
| 7 | Complaint/refund/damage/payment/B2B escalate | `test_high_risk_messages_escalate_to_human` |
| 8 | Mock mode admits demo, claims no real order | `test_completed_booking_admits_demo_mode_and_claims_no_real_order` |
| 9 | PII masking works | `test_mask_pii_masks_phone_and_email` / `_preserves_order_ids_and_times` |
| 10 | Quick actions rendered inside agent messages | `test_greeting_...` / `test_book_pickup_...` assert `body["actions"]` |
| — | Clicked action is not mis-escalated | `test_clicked_cancel_action_is_not_treated_as_escalation` |
| — | Config wiring sanity | `test_service_buttons_match_service_catalog_config`, `test_welcome_and_refusal_come_from_config` |

## Manual smoke (live mock server)

```bash
cd "apps/whatsapp-agent"
.venv/Scripts/python.exe -m uvicorn main:app --host 127.0.0.1 --port 8100
```

Then POST to `http://127.0.0.1:8100/api/test-chat/message`:

| Send `{"message": ...}` | Expect |
|---|---|
| `"Hi"` | welcome text + 6 main-menu actions |
| `"Book Pickup"` (+`action_id`) | "which service?" + 7 service actions |
| `"I want a refund for my order"` | handoff message, `provider:"none"`, `call_support` action |
| `"How much for curtains?"` | no `AED` number, "team will confirm" |
| `"Wash & Fold\nDubai Marina\ntomorrow"` | booking summary + "Demo mode…" |
| `"Can you write python code?"` | configured refusal, `domain:"out_of_domain"` |

## Config edit test (no code change)

1. Edit `config/laundry_services.json` — add a service (key/label/keywords).
2. Restart the server.
3. `Book Pickup` now shows the new service button. Revert after testing.
