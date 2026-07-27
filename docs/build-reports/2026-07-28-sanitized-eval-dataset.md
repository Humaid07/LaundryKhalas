# Build Report — PII Sanitiser + Evaluation Dataset (Agent Hardening Slice 6)

- **Date:** 2026-07-28
- **Objective:** Never use raw six-month WhatsApp data as an unrestricted prompt corpus. Provide a PII sanitiser + a structured, sanitised evaluation-record format (with seed examples) so historical chats can be converted into safe, structured eval/tuning data — targeting the approved rules + desired style, not a copy of past agent behaviour.

## What was built
- **`services/sanitize.py`** (pure) — `sanitize_text` masks emails, URLs, order IDs, phone numbers, long digit runs (accounts/cards), rough full-address hints, and API keys; optional explicit name masking. `sanitize_record` drops raw-PII fields entirely and scrubs free-text fields.
- **`services/eval_dataset.py`** — the eval-record schema (required keys), the 20 evaluation groups, `validate_record` (missing keys / PII keys / unknown group), `to_eval_record` (builds a **sanitised** record from raw parts), and a cached loader for the seed dataset.
- **`eval/evaluation_dataset.json`** — 11 synthesised, PII-free seed records across the key groups (fragmented booking, price-enquiry converted/not, discount request, bespoke, complaint, B2B, order edit, prompt injection, duplicate message, repeat customer). Each carries expected extraction / tool calls / response / **forbidden** behaviour / funnel stage / service category / country / outcome.

## Why
The spec is explicit: sanitise, classify and convert history into safe structured examples before any evaluation/tuning; learn customer phrasing and failure patterns, but make the *target* the approved business rules. This slice provides the format + the guardrail (sanitiser) + a validated seed set.

## Database / agent / API / UI
- **None** — pure services + a JSON data file + tests. No migration, no endpoints, no agent behaviour change.

## Tests run + results
- **`tests/test_sanitize_eval.py` — 9 passed** (masks phone/email/URL/order-id/address/long-digits/API-key; names masked only on request; `sanitize_record` drops PII fields + scrubs text; seed dataset loads + every record validates + no PII keys + key groups covered; `to_eval_record` sanitises; validator flags missing keys + PII).
- Targeted run only (no DB, no migration); full-suite regression unaffected (additive files).

## Known limitations
- The seed set is 11 synthesised examples — the full dataset is generated from history by piping records through `sanitize`/`to_eval_record` (generation job not included here).
- General name detection is intentionally not attempted (too lossy); known names are passed explicitly.
- No automated eval *runner* yet (records are the ground truth; a harness that replays them against the agent is a follow-up).

## Security / privacy notes
- This slice IS the privacy guardrail for evaluation data: raw-PII fields are dropped, free text is scrubbed, and the validator rejects any record that still carries PII keys. No real customer data is included — all seed records are synthesised.

## Commands
- Tests: `cd apps/whatsapp-agent && ./.venv/Scripts/python.exe -m pytest tests/test_sanitize_eval.py -q`

## Next recommended step
Slice 7 — campaign attribution (mock-first): a campaign table + last-touch attribution (7/14/30d) + eligibility validation from config campaigns, a `campaign_responder` segment feed, and a `get_campaign_eligibility` grounding tool. (HubSpot sync slice dropped at the owner's request — no HubSpot instance.)
