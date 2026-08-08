# Build Report — Knowledge Reinforcement Phase 2 (Retrieval KB from real chats)

- **Date:** 2026-08-08
- **Design spec:** `docs/superpowers/specs/2026-08-08-knowledge-reinforcement-design.md`
- **Follows:** Phase 1 (`docs/build-reports/2026-08-08-knowledge-reinforcement-phase1-rules.md`)
- **Source material (NOT committed):** `C:\Users\HP\Downloads\Whatsapp agent knowledge reinforcing material\chats_html.zip`
  (533 real WhatsApp chats, WhatsApp-export HTML).

## Objective

Give the WhatsApp agent a grounded, **PII-free** retrieval tool
(`search_past_conversations`) that surfaces redacted precedent from real past
customer chats — *how* a request was phrased/handled — without ever exposing raw
customer data. "Learning" here is grounding, not fine-tuning; embeddings are
computed **locally** (no external vendor), honoring CLAUDE.md §5/§7.

## What was built

### 1. Local embedding + cosine retrieval service — `services/chat_kb.py`
- `fastembed` (BAAI/bge-small-en-v1.5, 384-dim, ONNX) loaded **lazily** and cached.
- `search(query, market, k, min_score)` embeds the query locally and does a
  pgvector cosine lookup (`1 - (embedding <=> query)`), returning only snippets
  at/above `min_score` (default 0.30).
- **Fail-soft by design:** empty query, non-supabase mode, missing model, or DB
  error → returns `[]`. Retrieval can never break a customer turn.

### 2. pgvector table — migration `20260808_000051_chat_knowledge_base.sql`
- `chat_knowledge_base` (id, source_ref, chunk_index, market, content,
  `embedding vector(384)`, token_estimate, `dedupe_key unique`, created_at).
- HNSW cosine index + market index. **RLS deny-all** (only the service role, which
  bypasses RLS, reads/writes) — even redacted precedent is never exposed to
  anon/end-user roles. Deployed to dev/test Supabase.

### 3. Offline indexer — `scripts/index_chat_kb.py`
- Parses `chats_html.zip` (one HTML per contact, stable export markup), **redacts
  PII**, chunks into overlapping 8-message windows (2 overlap), embeds locally in
  batches of 256, and upserts (`on conflict (dedupe_key) do nothing` → re-runnable).
- `source_ref` is a **salted SHA-1 hash** of the contact — the raw number is never
  stored. Market inferred from country code (974→QA else AE).

### 4. Redaction hardening — `services/sanitize.py`
- Existing `sanitize_text` scrubs phones/emails/URLs/order-IDs/addresses/long-digit
  runs/API-keys.
- **NEW `scrub_conversational_names()`** — targeted, low-lossy name redaction: masks
  a capitalised name **only** when it follows an intro phrase ("I'm X", "this is X",
  "my name is X", "call me X", …) and isn't a common non-name word. The indexer also
  masks the saved contact display-name. General/blanket name detection is
  intentionally avoided (too lossy — would shred service/place/brand names and hurt
  retrieval).

### 5. Agent tool — `search_past_conversations` (in `booking_tools.py`)
- Registered in `BOOKING_TOOL_SCHEMAS`; dispatcher calls `chat_kb.search(...)` and
  returns snippets with a hard-wired note: *"Guidance only — never quote a
  price/turnaround/policy from these."* Prices/policy still come only from the
  catalogue/pricing tools. Schema description reinforces the same boundary.

## Redaction audit (evidence)

Ran the full 533-chat archive through the exact indexer parse+redact path and
measured residual PII on the resulting ~4,034 chunks (audit prints only
post-redaction text):

| Signal | Baseline (structural only) | With targeted name scrub |
|---|---|---|
| Intro-phrase name leakage (hits) | 42 | **0** |
| Distinct residual first-names | 25 | **0** |
| Phones / emails / addresses / URLs | masked | masked |

The earlier "935 names" figure was a **measurement artifact** (a case-insensitive
regex counting benign words like "fine"/"Ok" after intro phrases), not real
leakage — corrected to a case-sensitive metric.

## Indexing result

- Chats parsed (non-empty): **493 / 533**  (40 had no extractable messages).
- Chunks indexed: **4,034** across **489 distinct chats** (markets: AE 3,382 / QA 652).
  All redacted through the name-scrub path.
- **Indexer perf fix during this run:** the embedder's default batch size (256) padded
  every chunk in a batch to bge-small's 512-token max, building a huge tensor that took
  *minutes* per batch on CPU — the earlier re-index runs looked "hung" and never got past
  the first batch (only 256/37-chat rows landed). Root-caused to embedding-batch width
  (single embeds and small batches were fine); fixed by setting `EMBED_BATCH = 16` in
  `services/chat_kb.py` (~40s per 256 chunks, steady). Also made the indexer **resumable**
  (skips already-stored `dedupe_key`s before the embed step) and hardened its DB writes
  (fresh short-lived connection per batch + per-call timeout + retry, instead of holding
  one connection across the slow embed — the Supabase pooler was dropping that idle socket).
  Final run: 3,778 new chunks embedded+upserted in one clean pass, HNSW index rebuilt.

## Retrieval verification (live)

Ran 5 real queries through `chat_kb.search` against the populated Supabase table
(real embedding + real pgvector lookup), `k=3`, `min_score=0.30`:

| Query | Hits | Top cosine |
|---|---|---|
| "wash and fold price per kg" | 3 | 0.810 |
| "do you deliver same day" | 3 | 0.797 |
| "curtain cleaning" | 3 | 0.714 |
| "leather jacket cleaning" | 3 | 0.710 |
| "wedding dress dry clean" | 3 | 0.752 |

- All 5 queries returned relevant precedent (every top score well above the 0.30 floor).
- Verified `idx_chat_kb_embedding` (HNSW cosine) is present after the run.
- Raw-PII scan (phones/emails regex) across all returned snippets: **0** leaks.

## Files

**Created:** `services/chat_kb.py`, `scripts/index_chat_kb.py`,
`tests/test_chat_kb.py`, `supabase/migrations/20260808_000051_chat_knowledge_base.sql`.
**Modified:** `services/sanitize.py` (+`scrub_conversational_names`),
`agents/whatsapp_agent/booking_tools.py` (tool registration + dispatch),
`tests/test_sanitize_eval.py` (4 name-scrub tests), `pyproject.toml` (`[kb]` extra).

## Dependencies

- New **opt-in** extra `kb = ["fastembed>=0.8.0"]` (pulls onnxruntime — heavy).
  `services/chat_kb.py` lazy-imports it and fails soft when absent, so the base
  install and the hermetic test suite need nothing extra. Enable retrieval / run
  the indexer with `pip install .[kb]`.

## What is mock-only / live / deferred

- **Local, no external calls:** embeddings run on-device (fastembed/ONNX). No
  Anthropic/OpenAI/embedding-vendor call is made — consistent with §5.
- **Live (dev/test):** the pgvector table and retrieval tool are live against the
  dev/test Supabase; the agent can call `search_past_conversations` now.
- **Deferred:** the 452 MB `WhatsApp_All_Chats.zip` (media) is never used/committed;
  a scheduled re-index job; per-market tuning of `min_score`/`k`.

## Tests run

- `tests/test_chat_kb.py` — **8 passed** (retrieval shape, fail-soft paths, tool
  registration + dispatch, indexer parse redaction).
- `tests/test_sanitize_eval.py` — **13 passed** (incl. 4 new name-scrub tests).
- Full backend suite — **1,807 passed**, 0 failed, 9 warnings (14m18s), hermetic
  (mock LLM, sqlite pin — the embedder/pgvector path is mocked in tests).

## Security / privacy notes

- Raw chats + the 452 MB archive are **never committed**; only redacted text +
  vectors reach the DB. `source_ref` is a salted hash. RLS deny-all. Targeted name
  redaction added on top of structural PII scrubbing. Honors §5 (no secrets / no
  live external calls) and §7 (privacy firewall).

## How to verify manually

```
cd apps/whatsapp-agent
pip install .[kb]                      # fastembed (one-time; downloads ONNX model)
# DATABASE_MODE=supabase in env
python scripts/index_chat_kb.py "<path>/chats_html.zip"   # re-runnable
python -m pytest tests/test_chat_kb.py tests/test_sanitize_eval.py -q
```
Then drive a WhatsApp flow and confirm the agent can pull redacted precedent via
`search_past_conversations` (guidance only; never a price source).

## Next recommended step

Commit Phase 1 + Phase 2 to main (per standing rule, on request), then wire a
periodic re-index and tune retrieval thresholds against live usage.
