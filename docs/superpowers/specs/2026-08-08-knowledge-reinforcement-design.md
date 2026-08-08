# Knowledge Reinforcement (Rules + Retrieval KB) — Design

- **Date:** 2026-08-08
- **Status:** Approved (pending written-spec review)
- **Scope:** `apps/whatsapp-agent` — config/prompt (Phase 1); PII redaction + pgvector retrieval (Phase 2)
- **Source material:** `C:\Users\HP\Downloads\Whatsapp agent knowledge reinforcing material\`
  (`Whatsapp agent rules for every service.docx`, `LaundryKhalas_WhatsApp_Agent_Master_Prompt_1.md`,
  `LaundryKhalas_Pricing_Questions.docx`, `chats_html.zip` = 533 real chats, `WhatsApp_All_Chats.zip` = 452 MB media — NOT used).

## Goal

Make the WhatsApp agent reliably follow the founder's documented rules, and let it
look up redacted precedent from real past chats at runtime. Verifiable in
production ("is it picking up the rules?").

## Honest framing (no ML training)

Claude is not fine-tuned. "Learning" here = **grounding**: (1) rules encoded into
the config the system prompt loads every turn; (2) a retrieval tool the agent can
call for redacted precedent. Anthropic has no embeddings API, so retrieval uses a
**local** embedding model (no vendor, PII stays local).

## Decomposition

Too large for one implementation pass — split into two sub-projects, built in
order. Phase 1 ships and is production-verified before Phase 2 starts.

---

## PHASE 1 — Rules → config + prompt  (this spec, full detail)

### Reconciliation policy (confirmed)

**Newest doc wins, confirm each clash.** Precedence: `pricing-questions.docx`
(Aug 4) > `master-prompt.md` (Jul 31); live config is the current baseline. For
every conflict I present `docs value(s) + dates + current config value` and get a
yes/no BEFORE encoding. No silent changes. Known conflicts to raise up front:
- **Min order / delivery:** docs (Aug 4) = 30 free / else fee; master prompt
  (Jul 31) = 50 free / 8 AED. Live config = 30 free / 10 fee. → confirm keep 30/10.
- **Express:** master prompt = "+50%, 3 PM cutoff"; rules docx = "same-day 8–12 hr,
  +50%". → confirm surcharge 50% + cutoff value.
- Any per-service price/rule that differs from `laundry_catalogue.json` / current rules.

### Extraction → encoding

1. Extract text from the 3 docs (docx via `word/document.xml`; md direct) into a
   structured rule list grouped by service + global.
2. Map each rule to its config home (existing files, editing values in place):
   - Global: `config/whatsapp_agent_rules.json`, `config/fulfilment_charges.json`,
     `config/order_discounts.json` / `negotiation.json`, `config/delivery_sla.json`.
   - Per-service: `config/laundry_catalogue.json`, `config/service_rules` registry,
     `config/specialty_routing.json`, `config/alterations.json`.
   - Tone/persona: `config/agent_tone_rules.json`, `config/persona.json`.
   - Knowledge/coverage: `config/laundrykhalas_knowledge.json`.
3. For genuinely new rule categories with no config home, add a clearly-named key
   (or a new `config/service_qa.json`) and load it via `rules.py` into the prompt.
4. Update `agents/whatsapp_agent/prompts.py` only if a new config source needs
   wiring; prefer extending existing loaders.

### Testing

- Unit: for each changed config value, a test asserting the loader/prompt reflects
  it (extend existing `tests/test_service_rules*.py` / pricing tests).
- Prompt-assembly test: the new/changed rules appear in the assembled system prompt.
- Production: bring the stack up, drive the relevant flows on WhatsApp, confirm the
  agent quotes/behaves per each confirmed rule.

### Files touched (Phase 1)

`config/*.json` (values), possibly one new `config/*.json`, maybe
`agents/whatsapp_agent/prompts.py` + `rules.py`, config tests. **PII-free →
committed + pushed.**

---

## PHASE 2 — Retrieval KB from 533 chats  (outline; own spec before build)

Pipeline: `chats_html.zip` → parse per-contact HTML → **redact PII**
(`services/privacy.py` + `sanitize.py`: phones/emails/names/addresses) → chunk
into exchanges → embed locally with **fastembed (bge-small-en, ONNX)** → store in
a new **Supabase pgvector** table (new migration) → expose a grounded
`search_past_conversations` tool wired into `booking_tools` + `prompts.py`.

Key characteristics:
- Offline one-time indexing script (`scripts/index_chat_kb.py`); re-runnable.
- New dependency: `fastembed`. New migration: pgvector table (embeddings + redacted text + metadata).
- Retrieval tool returns redacted snippets only; never raw PII; describe-only (no invented facts).
- **Raw chats + the 452 MB zip are NEVER committed.** Only scripts, migration, tool, tests.
- Tests: redaction removes PII (property tests), chunker, retrieval tool shape (mock embed), end-to-end index→query on a tiny fixture.

Phase 2 gets its own detailed design doc + plan once Phase 1 is shipped and verified.

## Git / privacy summary

Committed: config rule changes, redaction+indexing scripts, pgvector migration,
retrieval tool, tests, docs. Never committed: raw customer chats, the 452 MB
archive, any un-redacted PII. Honors CLAUDE.md §5 (no secrets) + §7 (privacy firewall).

## Rollout

Phase 1: config-only, reversible via git. Phase 2: new table (migration) + flag to
enable retrieval; local embeddings mean no external calls.
