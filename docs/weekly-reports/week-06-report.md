# Week 06 Report — Knowledge Reinforcement + Dev Facility Switcher

**Week of:** 2026-08-07 (covers 2026-08-07 → 2026-08-08)

## 1. Executive summary
Two things shipped. First, a two-phase **knowledge reinforcement** program that
makes the WhatsApp agent answer from grounded sources instead of prose: Phase 1
folded the per-service rulebook into the catalogue/SLA/routing **configs** (so
rules are data, not prompt text), and Phase 2 gave the agent a **PII-free retrieval
KB** built from real past customer chats — it can look up *how* a similar request
was handled without ever seeing raw customer data. Second, a small **dev-only
facility switcher** so a developer can view the facility dashboard as any active
facility. All work is committed and pushed to `main`; the full backend suite is
green (1,807 passed).

## 2. What shipped this week
- **Phase 1 (rules → config):** SLA corrections (curtain, alterations, mascot,
  restoration), a new `LEATHER_CARE` catalogue category, wedding-dress migrated to
  a quotable range, evening-dress pricing fixed, and B2B same-day keyword coverage
  (gym/spa/factory/manufacturing). 90%+ of the written rulebook is now encoded in
  config; the earlier migration/config gaps (000039–045 era) were normalized.
- **Phase 2 (retrieval KB):** `services/chat_kb.py` (local embeddings + pgvector
  cosine search), migration `000051` (`chat_knowledge_base`, HNSW, RLS deny-all),
  `scripts/index_chat_kb.py` (parse → redact PII → chunk → embed → upsert), a
  targeted name-redaction pass in `services/sanitize.py`, and a new agent tool
  `search_past_conversations` (guidance only — never a price/policy source).
- **Dev facility switcher:** header dropdown (self-hides below 2 facilities),
  `GET /api/facility/switchable`, and an `X-Facility-Id` override gated to the dev
  branch of `api/deps` — never active in production auth.

## 3. What changed since last update
The agent now grounds phrasing/handling in redacted precedent from **4,034 chunks
across 489 real chats** (indexed to the dev/test Supabase), and service rules are
resolved from config rather than prompt prose. No customer-facing pricing or policy
path changed — prices/policy still come only from the catalogue/pricing tools.

## 4. Screens/features ready to demo
- WhatsApp agent answering a service question and (behind the scenes) pulling
  redacted precedent via `search_past_conversations`.
- Facility dashboard header **facility switcher** (dev) flipping between facilities.
- Retrieval quality check: 5 sample queries returning relevant snippets with
  cosine scores 0.71–0.81 and zero PII.

## 5. Backend progress
New `services/chat_kb.py` and `scripts/index_chat_kb.py`; `services/sanitize.py`
gained `scrub_conversational_names()`; `booking_tools.py` registers + dispatches
`search_past_conversations`; catalogue/SLA/routing configs and `services/b2b.py`
updated for Phase 1. `fastembed` added as an **opt-in `[kb]` extra** (lazy-imported,
fails soft when absent). Facility switcher: `api/facility.py` + `api/deps.py`.

## 6. Frontend progress
New `FacilitySwitcher.tsx`, header mount, `X-Facility-Id` injection in the API
client, and dev facility-id persistence in `auth-token.ts` (facility dashboard).

## 7. Agent progress
One new grounded tool (`search_past_conversations`) wired for **guidance only**,
with the price/policy boundary reinforced in both the schema description and the
dispatcher's returned note. Phase 1 rule encoding means the agent resolves
service SLAs/pricing/routing from config, not prose.

## 8. Database progress
Migration **000051** (`chat_knowledge_base`: `vector(384)`, HNSW cosine index,
market index, `dedupe_key` unique, RLS deny-all) authored **and deployed** to the
dev/test Supabase. Table populated with 4,034 redacted chunks (AE 3,382 / QA 652).
No SQLite/ORM mirror — retrieval is Supabase/pgvector-only; the hermetic test suite
mocks the embedder.

## 9. Security/privacy progress
Only **redacted** text + vectors reach the DB — never raw PII. `source_ref` is a
salted SHA-1 hash of the contact (raw number never stored); message bodies pass
through structural PII scrubbing (phones/emails/URLs/addresses) plus targeted name
redaction. RLS deny-all means even redacted precedent is unreachable by anon/end-user
roles. Retrieval and indexing run **entirely locally** (fastembed/ONNX) — no
Anthropic/OpenAI/embedding-vendor call, consistent with CLAUDE.md §5/§7. Live PII
scan across returned snippets: **0 leaks**. The 452 MB media archive is never used
or committed.

## 10. Testing progress
Full backend suite: **1,807 passed**, 0 failed (14m18s, hermetic — mock LLM, sqlite
pin). New `tests/test_chat_kb.py` and expanded `tests/test_sanitize_eval.py`
(name-scrub); Phase 1 test files updated for the new rules. The seed-isolation race
noted in week 05 did **not** recur in this full run.

## 11. Blockers
None.

## 12. Risks
Retrieval only serves where the opt-in `[kb]` extra is installed and
`DATABASE_MODE=supabase`; elsewhere the tool fails soft (returns nothing), which is
safe but means precedent grounding is silently unavailable. Name redaction is
deliberately conservative (intro-phrase + saved-contact only) to avoid shredding
service/place/brand names — a rare unusual name phrasing could slip a first name;
structural PII (numbers/emails/addresses) is always masked.

## 13. Decisions needed from founder/team
Whether to schedule a periodic re-index job (so the KB tracks new conversations),
and whether to enable the `[kb]` extra in the live/staging deploy so the agent can
use `search_past_conversations` in production.

## 14. Deviations from roadmap/spec
Phase 2's Phase-2 report originally targeted a full truncate-and-rebuild; the actual
run indexed **resumably** on top of the existing rows (idempotent `dedupe_key`).
During indexing, an "it hangs" symptom was root-caused to the embedder's default
batch width (256 padded every chunk to bge-small's 512-token max → minutes per
batch); fixed with `EMBED_BATCH=16` and hardened DB writes — see the Phase 2 build
report. The external `.blueprint/` tooling descriptor was gitignored, not committed.

## 15. Next week's plan
Optionally schedule the re-index and tune per-market retrieval thresholds against
live usage; decide on enabling the `[kb]` extra in staging; from the deferred design
spec, scope the inbound-image (WhatsApp photo → vision → knowledge) feature if
prioritized.

---

**Commits (all on `main`, pushed):** facility switcher `8141326`; knowledge
reinforcement `473ab43`; inbound-image-vision spec `4d6feea`.
**Build reports:** `build-reports/2026-08-08-knowledge-reinforcement-phase1-rules.md`,
`build-reports/2026-08-08-knowledge-reinforcement-phase2-retrieval.md`,
`build-reports/2026-08-07-facility-switcher-dev.md`.
