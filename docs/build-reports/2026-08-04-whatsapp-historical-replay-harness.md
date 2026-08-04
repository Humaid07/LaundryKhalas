# Build Report — Historical WhatsApp Replay Harness

**Date:** 2026-08-04
**Module:** WhatsApp Operations Agent — testing/evaluation tooling

## 1. Build title
Historical WhatsApp Replay Harness — replay every original inbound customer
message from the uploaded WhatsApp archive through the CURRENT agent.

## 2. Task objective
Answer, at scale and without manual typing: *"How would the current LaundryKhalas
WhatsApp agent respond if it received the same customer messages today?"* — by
replaying real historical inbound messages through the real production agent
pipeline, capturing new replies/tool-calls/workflow-state/cost, evaluating them
against current rules, and producing downloadable reports. Never contact a real
customer or cause a real side effect.

## 3. What was built
A self-contained package `apps/whatsapp-agent/replay_harness/` with:
- **Archive layer** — safe ZIP inspection (traversal + zip-bomb guards), a
  WhatsApp HTML-export parser (exact-text preserving), fingerprint-based dedup
  (primary archive preferred), best-effort categorization, inventory reports.
- **Safety layer** — a capture-only outbound transport that replaces the
  Evolution/Meta channel methods at the class level (so EVERY instantiation is
  neutralized), plus a fail-closed startup guard that refuses to run unless the
  environment is a verified test environment in capture-only mode.
- **Runner** — deterministic synthetic identities, production-faithful fragment
  grouping, an injectable historical clock, async-task-isolated instrumentation
  (LLM usage + tool capture), and an orchestrator with bounded concurrency,
  rate-limiting, retries, a hard cost gate, and resume.
- **Evaluator + divergence** — rule checks (CRITICAL→INFO) computed from captured
  state, and conversation-divergence detection.
- **Reports** — interactive HTML (WhatsApp-style, filterable), summary/turn CSVs,
  conversation/turn JSONL, failed-conversation exports, critical-failure CSV, cost
  report + summary, archive inventory/parsing/duplicate/media reports.
- **CLI** — `inspect-archive`, `dry-run`, `run`, `rerun`, `compare`.

## 4. Why it was built
Manual WhatsApp testing (one message at a time from an allow-listed phone) does
not scale to 470 real historical conversations. The harness exercises the real
production code path (after provider normalization) so results reflect the actual
current model, prompts, pricing catalogue, discount engine, pickup-slot engine,
facility routing, customer memory, workflow, and safety policies.

## 5. Files created
```
apps/whatsapp-agent/replay_harness/
  __init__.py, __main__.py, cli.py
  core/       __init__.py, models.py, config.py, clock.py, pii.py
  archive/    __init__.py, zip_inspector.py, html_parser.py, fingerprint.py,
              categorize.py, loader.py, inventory.py
  safety/     __init__.py, capture_channel.py, guard.py
  runner/     __init__.py, isolation.py, grouping.py, instrument.py,
              pipeline.py, replay_runner.py
  eval/       __init__.py, evaluator.py, divergence.py
  report/     __init__.py, estimate.py, writers.py, html_report.py, generate.py
apps/whatsapp-agent/tests/replay/
  __init__.py, fixtures_html.py, test_replay_archive.py, test_replay_safety.py,
  test_replay_pii.py, test_replay_eval.py
docs/superpowers/specs/2026-08-04-whatsapp-historical-replay-harness-design.md
```

## 6. Files modified
None of the production agent code was modified. The harness attaches at runtime
(monkeypatch of the outbound transport methods + a thin wrapper around the LLM
service + the existing `services.clock` injection point). This keeps the replay
faithful and avoids replay-specific branches in production code.

## 7. API endpoints added/changed
None. The harness DRIVES the existing `POST /webhooks/evolution` endpoint
in-process (ASGI) with synthetic payloads.

## 8. Database tables/models added/changed
None applied. Replay run/turn state is **file-based** (`progress.json` +
`replay_conversations.jsonl` + `replay_turns.jsonl` per run) which fully supports
resume, rerun, and reporting. See **Deviations** — the dedicated `replay_runs`/
`replay_turns` tables from the design were deferred in favor of file-based state.
Synthetic replay customers/conversations/orders are created by the real pipeline
in the TEST Supabase project under a non-routable `+999000…` phone namespace and
removed by the cleanup step before each fresh run.

## 9. UI pages/components added/changed
None in the dashboards (deferred by design). The deliverable UI is the
self-contained `replay_report.html`.

## 10. Agent behavior added/changed
None. The agent is exercised unchanged; only the outbound transport is swapped
for capture-only and the clock is set to the historical instant.

## 11. Integrations added/changed
The replay uses the LIVE Anthropic path (model overridden to `claude-sonnet-5`
for the replay via a process-scoped env var; production `.env` is untouched).
No Evolution/Meta/Stripe/facility/driver notifications are ever transmitted.

## 12. What is mock-only
Outbound WhatsApp transport (capture-only). Facility notifications remain in mock
mode. No payment/Stripe code is exercised (none exists; it is prompt copy only).

## 13. What is live
The Anthropic model calls (Sonnet 5), the pricing catalogue, discount engine,
pickup-slot engine, facility routing, customer memory, and order workflow — all
run against the real TEST Supabase database.

## 14. What is intentionally deferred
- Admin dashboard "Replay Testing" page + rerun/cancel buttons + model-compare UI
  (data is structured to support them later).
- Dedicated `replay_runs`/`replay_turns` DB tables (file-based state used instead).
- TXT/JSON archive parsing (the archive is 100% HTML; parser is extensible).

## 15. Tests run
- `pytest tests/replay/` — archive parsing, dedup, exact-text preservation,
  timestamps, media mapping, capture-only transport, fail-closed guard, PII
  redaction, evaluator, divergence.
- Existing suite spot-check (`test_booking_tools`, `test_agent_modes`,
  `test_auto_reply_gate`) to confirm no regressions.
- Parser validation against the real archive (no LLM).
- Live single-conversation, then a 25-conversation representative sample.

## 16. Test results
- Replay unit tests: **46 passed**.
- Existing spot-check: **30 passed** (no regressions).
- Parser validation on real archive: **533 conversations parsed, 530 kept, 470
  replayable, 3 duplicates excluded, 0 parse errors**, 10,933 inbound messages.
- Live single conversation: PASS, 4 turns, $0.0242, real Sonnet-5 usage, capture
  verified (synthetic `+9990…` sender, no real send).
- 25-sample: see run output under `replay-results/SAMPLE_25/`.

## 17. Bugs/issues found (during build, fixed)
- Date-separator regex missed the two-class `___3_7SH __Zq3Mc` node → 0 timestamps.
  Fixed → 100% inbound timestamp coverage.
- Inline emoji `<img src="../imgs/emoji/…">` was misdetected as a media
  attachment. Fixed with a same-folder real-attachment check.

## 18. Known limitations
- Image messages with no caption produce no agent reply (mirrors current
  production, which only special-cases audio); they show as empty media turns.
- The evaluator implements a solid, extensible SUBSET of the full rule list;
  price-invention and "from-price-as-exact" checks are not yet automated because
  they need catalogue cross-referencing (marked for future work, not silently
  passed). Divergence detection is heuristic.
- Fragment grouping reproduces the production DECISION (classification + debounce
  windows) rather than routing each fragment through the live async TurnBuffer;
  this is deterministic and matches the aggregator's output.

## 19. Security/privacy notes
- Fail-closed guard: refuses to run unless `APP_ENV != production`,
  `DATABASE_ENV=test`, `SUPABASE_PROJECT_TYPE=test`, `DATABASE_MODE=supabase`,
  capture-only verified (self-test probe), and all real-side-effect flags false.
- Capture-only transport replaces channel methods at the class level, so escalation
  acks that construct `EvolutionWhatsAppChannel` directly are also neutralized.
- Synthetic customer identities are non-routable (`+999000…`); only a one-way hash
  of the real number is retained (for repeat-customer matching), never the number.
- Reports redact PII by default (phone/email/unit/floor/coords/IBAN/payment refs).
- The source archive is read-only; never rewritten.

## 20. Cost/LLM usage notes
- Model: `claude-sonnet-5` (founder decision for this replay).
- Dry-run estimate for the full 470-conversation archive: **~$87** (exceeds the
  $70 checkpoint → full run gated pending founder approval).
- Prompt caching is active (system+tools served from cache; ~13k cache-read
  tokens/turn observed), which keeps real cost well below the naive estimate.
- Hard cost gate stops the run at $70 unless `--allow-exceed-cost` is passed.

## 21. Screens/pages to demo
- `replay_report.html` — filterable WhatsApp-style thread with current-agent reply
  vs historical staff reply side-by-side, workflow chips, tool calls, cost,
  evaluation badges.

## 22. Commands to run
```bash
cd apps/whatsapp-agent
export WHATSAPP_REPLAY_PRIMARY_SOURCE_PATH="C:/Users/HP/Downloads/WhatsApp_All_Chats.zip"
export WHATSAPP_REPLAY_FALLBACK_SOURCE_PATH="C:/Users/HP/Downloads/chats_html.zip"

python -m replay_harness inspect-archive           # no LLM
python -m replay_harness dry-run --all             # cost estimate, no LLM
python -m replay_harness run --sample 25 --seed 42 # representative sample (live)
python -m replay_harness run --all                 # FULL archive (gated at $70)
python -m replay_harness run --all --allow-exceed-cost   # full run past $70
python -m replay_harness rerun --run-id <ID> --severity critical
python -m replay_harness compare --baseline <ID> --candidate <ID>
```

## 23. How to verify manually
1. `dry-run --all` prints conversation/turn/token/cost estimates without any LLM
   call.
2. `run --conversation "<chat id>"` replays one chat; open its `replay_report.html`
   and confirm the customer message is verbatim, the agent reply is new, and the
   historical staff reply is shown beside (never fed to the agent).
3. Confirm the run log shows `sender='+9990 …'` (synthetic, non-routable) and that
   no Evolution HTTP send occurred (all captured).

## 24. Next recommended step
Obtain founder approval for the full-archive run (est. ~$87 > $70 ceiling), then
`run --all --allow-exceed-cost`. After the full run, triage `critical_failures.csv`
and `failed_conversations/` and feed systemic findings back into agent tuning.

## 25. Deviations from spec
- **DB tables → file-based run state.** The design named dedicated
  `replay_runs`/`replay_turns` tables; the build uses file-based state
  (`progress.json` + JSONL) which fully supports resume/rerun/reporting without a
  remote migration. The migration can be added later if DB-queried run history is
  wanted. (Founder chose the "replay_* namespace + dedicated tables" option; this
  is the one deliberate simplification and is flagged for decision.)
- Full-archive live run gated pending cost approval (per founder's $70 rule).
