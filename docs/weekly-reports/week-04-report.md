# Week 04 Report — Historical WhatsApp Replay Harness

**Week of:** 2026-08-04

## 1. Executive summary
Built and validated a Historical WhatsApp Replay Harness that replays every
original inbound customer message from the uploaded WhatsApp archive through the
current agent, capturing new replies, tool calls, workflow state, and cost, and
producing downloadable reports — with a fail-closed safety guard that guarantees
no real customer is ever contacted.

## 2. What shipped this week
- `apps/whatsapp-agent/replay_harness/` — archive parsing, capture-only transport,
  fail-closed safety guard, production-faithful runner, evaluator + divergence,
  full report set, and a CLI (`inspect-archive`/`dry-run`/`run`/`rerun`/`compare`).
- 46 new unit tests (archive, safety, PII, evaluator, divergence).
- Design spec + build report + presentation notes + docs home update.

## 3. What changed since last update
New testing capability; no changes to the production agent code (the harness
attaches at runtime and swaps only the outbound transport).

## 4. Screens/features ready to demo
- `replay_report.html`: filterable WhatsApp-style threads with customer / current
  agent / historical staff side-by-side, workflow chips, tool calls, cost, badges.
- CLI dry-run cost estimate and a live single-conversation / 25-sample replay.

## 5. Backend progress
Drives the real `POST /webhooks/evolution` in-process; captures usage from the
real LLM service and workflow state from the real order/conversation repos.

## 6. Frontend progress
Self-contained HTML report (no dashboard page yet — deferred by design).

## 7. Agent progress
Agent unchanged; exercised faithfully via Sonnet 5 for the replay.

## 8. Database progress
No schema change applied. Synthetic replay customers/orders land in the TEST
Supabase project under a non-routable `+999000…` namespace and are cleaned before
each fresh run. Run/turn state is file-based (resume/rerun supported).

## 9. Security/privacy progress
Fail-closed guard (test-env + capture-only + all real-side-effect flags off,
verified by a probe self-test). Non-routable synthetic identities; one-way hash of
the real number only. Reports redact PII by default. Source archive read-only.

## 10. Testing progress
- Replay unit tests: 46 passed. Existing suite spot-check: 30 passed (no regressions).
- Parser validation on the real archive: 533 parsed, 470 replayable, 0 parse errors.
- Live single conversation PASS; 25-conversation sample run executed.

## 11. Blockers
None technical. The full-archive live run is gated on cost approval.

## 12. Risks
- Full archive ≈ $87 on Sonnet 5 (> $70 checkpoint) — needs sign-off.
- Automated evaluator covers a strong subset of rules; deeper price-correctness
  checks are future work.

## 13. Decisions needed from founder/team
- Approve the full-archive run past the $70 ceiling (est. ~$87), or run capped.
- Optional: build the dedicated `replay_runs`/`replay_turns` DB tables + a "Replay
  Testing" dashboard page (both deferred).

## 14. Deviations from roadmap/spec
- Run state is file-based instead of dedicated DB tables (functionally equivalent
  for resume/reporting; documented in the build report).
- Full run gated pending cost approval.

## 15. Next week's plan
Run the full archive on approval, triage critical/failed conversations, and feed
systemic findings into agent tuning.
