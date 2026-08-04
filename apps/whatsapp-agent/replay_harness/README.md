# Historical WhatsApp Replay Harness

Replay every original **inbound customer** message from an exported WhatsApp
archive through the **current** LaundryKhalas WhatsApp agent, capture the new
replies + tool calls + workflow state + cost, evaluate against current rules, and
produce downloadable reports.

> **It never contacts a real customer.** The outbound transport is replaced by a
> capture-only adapter and a fail-closed guard aborts unless the environment is a
> verified test environment in capture-only mode.

## Quick start

```bash
cd apps/whatsapp-agent

# Point at the archives (defaults also search ./test-data/whatsapp and ~/Downloads)
export WHATSAPP_REPLAY_PRIMARY_SOURCE_PATH="C:/Users/HP/Downloads/WhatsApp_All_Chats.zip"
export WHATSAPP_REPLAY_FALLBACK_SOURCE_PATH="C:/Users/HP/Downloads/chats_html.zip"

python -m replay_harness inspect-archive              # inventory only, no LLM
python -m replay_harness dry-run --all                # cost/token estimate, no LLM
python -m replay_harness run --sample 25 --seed 42    # representative sample (LIVE)
python -m replay_harness run --all                    # full archive (gated at $70)
```

## How it stays faithful

It drives the real `POST /webhooks/evolution` endpoint in-process, so the full
production path runs: normalization → dedup → persistence → aggregation → customer
memory → conversation state → Anthropic agent → tool loop → workflow update →
deliver. The ONLY swapped component is the outbound transport. The model is
overridden to `claude-sonnet-5` for the replay via a process-scoped env var
(production `.env` untouched).

## Safety (fail-closed)

The run refuses to start unless ALL hold: `APP_ENV != production`,
`DATABASE_ENV=test`, `SUPABASE_PROJECT_TYPE=test`, `DATABASE_MODE=supabase`,
capture-only mode on + verified by a probe self-test, and every real-side-effect
flag false. Synthetic customers use non-routable `+999000…` numbers; only a
one-way hash of the real number is kept (matching only).

## Outputs (`replay-results/<run_id>/`)

`replay_report.html` (interactive), `replay_summary.csv`, `replay_turns.csv`,
`replay_conversations.jsonl`, `replay_turns.jsonl`, `failed_conversations/…`,
`critical_failures.csv`, `replay_cost_report.csv`, `replay_cost_summary.json`,
`archive_inventory.csv`, `archive_parsing_report.json`,
`duplicate_conversations.csv`, `unsupported_messages.csv`, `media_mapping_report.csv`.

## Key env vars

| Var | Default | Meaning |
|---|---|---|
| `WHATSAPP_REPLAY_MODEL` | `claude-sonnet-5` | Replay model override |
| `WHATSAPP_REPLAY_MAX_COST_USD` | `70` | Hard cost ceiling |
| `WHATSAPP_REPLAY_REDACT_PII` | `true` | Redact PII in reports |
| `WHATSAPP_REPLAY_TIMING_MODE` | `ACCELERATED_TIMING` | `ACCELERATED_TIMING`\|`ORIGINAL_TIMING` |
| `WHATSAPP_REPLAY_DATE_MODE` | `HISTORICAL_DATE_CONTEXT` | historical vs current clock |
| `WHATSAPP_REPLAY_CUSTOMER_MEMORY_MODE` | `CUSTOMER_HISTORY` | `CUSTOMER_HISTORY`\|`ISOLATED_CHAT` |
| `WHATSAPP_REPLAY_MAX_CONCURRENCY` | `5` | Concurrent conversations |
| `WHATSAPP_REPLAY_REQUESTS_PER_MINUTE` | `40` | Rate limit |

## Resume / rerun / compare

```bash
python -m replay_harness run --all --resume            # resume after interruption
python -m replay_harness rerun --run-id <ID> --severity critical
python -m replay_harness compare --baseline <ID> --candidate <ID>
```

Run state is file-based (`progress.json` + JSONL); completed conversations are not
re-run unless requested.

See the design spec:
`docs/superpowers/specs/2026-08-04-whatsapp-historical-replay-harness-design.md`.
