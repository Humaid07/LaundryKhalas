# Build Report — Persistent Per-Customer AI Persona System

**Date:** 2026-07-29
**Type:** Backend — persona assignment (mock-first)
**Follows:** WhatsApp agent tuning program. Replaces the single `agent_name` placeholder.

## Objective
Give the WhatsApp AI agent a **multi-persona name system**: one approved name pinned to each
customer for life (never changing across orders/conversations/restarts), assigned by a
balanced/deterministic backend strategy, injected into every Anthropic request, and kept
separate from human Operations staff. Claude may never invent a name off the list.

## Approved personas
`Sara, Maya, Zoya, Hanna, Sofia, Max, Ben` — config via settings
`AGENT_PERSONA_NAMES` / `AGENT_PERSONA_ASSIGNMENT_MODE=PERSISTENT_PER_CUSTOMER`.

## What was built
- **`settings.py`** — `agent_persona_names`, `agent_persona_assignment_mode`,
  `agent_persona_assignment_version` (env-configurable).
- **`services/persona_assignment.py`** (pure selection + orchestration):
  - `select_for_key()` — **deterministic customer hashing** (SHA-256 of the customer key → index).
    This is balanced (uniform hash) AND concurrency-safe by construction: the same customer always
    maps to the same name, so two simultaneous first messages cannot split.
  - `ensure_assigned(customer, repo)` — returns the persisted persona, or assigns + persists one on
    first contact (mirrors it onto the working dict). Idempotent.
  - `persona_from_customer()` — reads the persisted persona; ignores any name no longer approved.
  - `assistant_identity()` — the structured context block
    `{persona_id, display_name, organization: "Laundry Khalaas", persona_type: "VIRTUAL_ASSISTANT"}`.
- **Migration `000031`** — `customers.assigned_ai_persona_id / assigned_ai_persona_name /
  ai_persona_assigned_at / ai_persona_assignment_version` (+ index). Idempotent, with rollback.
- **`customers_repo.assign_ai_persona()`** — CONDITIONAL update (`where assigned_ai_persona_id is
  null`) so an existing persona is never overwritten; concurrent first messages → first write wins,
  both read the same value.
- **`api/evolution_webhooks.py`** — assigns the persona on inbound first contact (guarded; never
  blocks a reply).
- **`booking_tools.py`** — `_clock_block` (the per-turn backend context merged into every state
  block) now includes `assistant_identity` from the customer's persona. `_persona_intro()` rewritten
  to the founder's STABLE wording: *"You are {{assigned_ai_persona_name}}, the Laundry Khalaas
  WhatsApp virtual assistant … always use the exact backend name … never select, change or invent
  … introduce yourself naturally on the first meaningful interaction …"* + human-staff separation
  ("SEPARATE from the human Operations team … stay silent until it is handed back"). The name is NOT
  baked into the stable (cacheable) prompt — it arrives per-turn via `assistant_identity`.
- **`prompts.py`** (legacy path) + **`config/persona.json`** updated; dead single-name
  `rules.persona_name()` removed.

## Human-takeover separation
The AI turn is already paused during a human takeover (`services/human_intervention`); the persona is
persisted on the customer, so when the conversation is released back to AI the **same** persona is
restored automatically (it is read from the record each turn). The prompt keeps the persona separate
from human staff names.

## Files created
- `services/persona_assignment.py`, `supabase/migrations/20260729_000031_customer_ai_persona.sql`,
  `tests/test_persona_assignment.py`

## Files modified
- `settings.py`, `db/repositories/customers_repo.py`, `api/evolution_webhooks.py`,
  `agents/whatsapp_agent/booking_tools.py`, `agents/whatsapp_agent/prompts.py`, `rules.py`,
  `config/persona.json`, `tests/test_agent_prompt_persona.py`

## Tests run / results (honest)
`tests/test_persona_assignment.py` — 10 guarantees (all pass, 23/23 with the prompt suite in a clean
run): new customer → one approved persona; persisted; retained across conversations/orders; restart-
stable; simultaneous first messages cannot split; different customers can differ; only approved names
selectable; stale/unapproved persisted name ignored; backend name drives `assistant_identity` +
prompt forbids override; persona separate + paused during takeover; release restores the original.
Broad regression: 116 passed. (2 fixture ERRORS were the pre-existing conftest `seed_demo_orders`
`LK-AE-1024` collision under certain test orderings — unrelated to persona, which uses an in-memory
fake repo; the persona suite passes 23/23 in isolation.) ruff clean on all changed files.

## Deployment note
Apply migration `000031` to dev Supabase (manually via asyncpg, per project convention) before live
use; until then the webhook's persona-assignment is guarded and simply skips (logs `persona_assign_skipped`).

## Known limitations
- Assignment strategy is deterministic hashing (balanced + concurrency-safe). A least-assigned /
  weighted round-robin could be swapped in behind `select_for_key` later; persistence already
  guarantees stability regardless.
