# Build Report — Mock-Mode Verification & Live Readiness Check

**Date:** 2026-08-06
**Type:** Verification / staging session (no product code changed)

## Task objective

Test the WhatsApp agent **without spending Anthropic credits** (owner is low on
credits), confirm there are no bugs, and leave the system configured for live
use once credits are topped up.

## What was done

1. **Full test suite (mock-mode bug gate).** Ran the entire pytest suite for
   `apps/whatsapp-agent`. The suite is self-hermetic — `tests/conftest.py` pins
   `LLM_PROVIDER=mock`, `WHATSAPP_MODE=mock`, `DATABASE_MODE=sqlite`,
   `WHATSAPP_CLASSIFIER_ENABLED=false`, `STRIPE_MODE=mock` — so it runs entirely
   offline and burns **zero credits**.
2. **Running-app mock smoke test.** Booted the real ASGI app in a hermetic mock
   config (isolated SQLite DB, mock provider) and drove a full booking
   conversation through the real `POST /api/test-chat/message` endpoint.
3. **Live-readiness check.** Loaded the real `.env` and validated the live
   Anthropic config via `Settings().ai_status` + `validate_ai_config()` — with
   **no billable API call**.

## Test results

| Check | Result |
|---|---|
| Full suite (serial, ~23 min) | **1608 passed, 10 failed** |
| The 10 failures, re-run in isolation (4 files) | **66 passed, 0 failed** |
| Running-app mock smoke (end-to-end) | **PASS** — boots, replies every turn, `mode=mock`, no live calls |
| `validate_ai_config()` on real `.env` | **OK** (no misconfig) |
| **Product bugs found** | **None** |

### Root cause of the 10 full-suite failures

All 10 depend on the seeded demo orders (LK-AE-1024..1027). Symptoms:
`sqlalchemy.orm.exc.StaleDataError: UPDATE on messages/orders expected to update
1 row(s); 0 were matched`, "order LK-AE-1027 not seeded", and
`order_status == 'draft'` (expected `active`).

These are a **test-isolation race in the long serial full-suite run** — an
earlier test leaks ORM session/DB state that clobbers the conftest
`_reset_orders`/`seed_demo_orders` fixture for later tests. Confirmed by
re-running the four affected files in isolation: **66/66 pass**. This is the
documented seed-collision harness class resurfacing at 1608-test scale.

**It cannot affect live/production use:** in production each webhook request
gets its own DB session and there is no demo-seed fixture. It is a test-harness
quality issue only.

## What is mock-only vs live

- **Mock-only (this session):** all verification ran with the deterministic
  mock provider and offline SQLite — zero external calls, zero cost.
- **Live (unchanged):** `.env` was **never switched to mock** (the harnesses
  self-configure), so the system remains live-configured:
  `provider=anthropic`, `model=claude-sonnet-5`, `live_llm_ready=True`,
  classifier ready, `whatsapp_mode=evolution`, `agent_mode=test`,
  `auto_reply=True`. It works the moment credits are available.

## Known limitations

- **Mock conversation quality is intentionally weak.** The mock provider is
  rule-based (`llm/providers/mock.py`) and does not do real multi-turn
  slot-filling — e.g. it loses the thread after an unexpected input. Mock mode
  verifies plumbing/health, **not** conversational quality. Real coherence
  requires live Claude Sonnet 5.
- **Full suite is not deterministically green** due to the isolation race above
  (product logic is green in isolation). Hardening the harness for a
  deterministic full-suite green is a separate, optional task.

## Cost / LLM usage notes

- This session used **zero Anthropic credits**.
- Sonnet 5 **intro pricing** ($2/1M in, $10/1M out) runs **through 2026-08-31**
  (then $3/$15). Automatic on model id `claude-sonnet-5` — no flag needed.
- Owner's own anchor: replay harness ran 470 conversations for ~$87 ⇒
  ~**$0.185 per full conversation** (incl. classifier + tool rounds). ~$5 buys
  ~25-30 full conversations. Setting `WHATSAPP_CLASSIFIER_ENABLED=false` during
  testing ~halves per-message cost (the classifier is a 2nd Sonnet call, shadow
  / off the reply path).

## How to verify manually

- Zero-credit unit gate:
  `cd apps/whatsapp-agent && ./.venv/Scripts/python.exe -m pytest -q tests/test_orders.py tests/test_quick_actions.py tests/test_agent_rules.py tests/test_stripe_webhooks.py`
  → expect 66 passed.
- Live readiness (no billable call):
  `./.venv/Scripts/python.exe -c "from settings import Settings; s=Settings(); print(s.ai_status['live_ready']); s.validate_ai_config()"`

## Next recommended step

- **When credits are topped up (do it before Aug 31 for the intro rate):** run a
  short live Sonnet-5 conversation test via the Evolution stack (test number on
  the allow-list). Optionally set `WHATSAPP_CLASSIFIER_ENABLED=false` to halve
  cost during that test.
- **Optional, separate task:** harden test-harness isolation so the full serial
  suite is deterministically green (per-test DB isolation for the seed fixture).
