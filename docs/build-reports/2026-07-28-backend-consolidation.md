# Build Report — Backend Consolidation (single canonical runtime)

**Date:** 2026-07-28
**Type:** Consolidation / refactor only (no feature work, no behavior change).

## Objective
Remove the risk of two parallel agent/backend implementations by making
`apps/whatsapp-agent/` the single canonical runtime and archiving the legacy root
`app/` tree.

## Duplicate structures found
Two backend trees:
1. **Root `app/`** — early mock-first prototype: FastAPI + SQLAlchemy/Alembic +
   Celery/Redis + a LangGraph approval-workflow graph, run on **:8000** via root
   `docker-compose.yml`. 81 Python files (Jul-17 vintage).
2. **`apps/whatsapp-agent/`** — the live backend: FastAPI + Supabase/asyncpg +
   Evolution WhatsApp + Claude tool-use, run on **:8100**. Owns all current work.

Audit (full detail in [`docs/audits/backend-consolidation-audit.md`](../audits/backend-consolidation-audit.md))
confirmed **nothing outside `app/` imports it** except two legacy tooling files
(`alembic/env.py`, `scripts/seed_mock_data.py`), and the canonical backend uses no
celery/redis/alembic. The legacy `docker-compose.yml` even mis-pointed its `admin`
service at the old `:8000` backend — a real footgun.

## Canonical decision
`apps/whatsapp-agent/` is canonical (ADR:
[`docs/decisions/ADR-canonical-backend-runtime.md`](../decisions/ADR-canonical-backend-runtime.md)).
Dashboards call only it; Supabase (`supabase/migrations/`) is the single DB source
of truth.

## What was migrated
**Nothing.** The only unique legacy logic was the `whatsapp_operations` LangGraph
approval graph, which is **intentionally discarded** — the canonical backend already
has a superior live Claude tool-use orchestration + its own `laundry_class/`
LangGraph agent, and its concepts (safety filter, human approval) already exist as
the domain guard + escalation/human-takeover + approval flow. Migrating it would
re-create a second implementation (the exact risk being removed). The graph stays
readable in the archive for reference.

## What was archived
Moved verbatim (via `git mv`, history preserved) from repo root to
**`legacy/root-app/`**:
`app/`, `alembic/`, `alembic.ini`, `docker-compose.yml`, `Dockerfile`, `docker/`
(postgres.Dockerfile), `pyproject.toml`, `scripts/` (seed_mock_data.py,
init_extensions.sql). Added `legacy/root-app/README.md` (archive notice). The
legacy stack remains self-contained inside the archive (its `from app.` imports
resolve there), but is no longer a runnable second backend at the repo root.

## Files updated
- **New docs:** `docs/audits/backend-consolidation-audit.md`,
  `docs/decisions/ADR-canonical-backend-runtime.md`,
  `docs/architecture/repo-structure.md`,
  `docs/architecture/canonical-backend-runtime.md`,
  `legacy/root-app/README.md`, this report.
- **Updated:** root `README.md` (now points at the canonical :8100 backend + the
  canonical run commands, replacing the old :8000 `docker compose` instructions),
  `docs/00-Home.md` (links to the consolidation docs + canonical run commands).

## Imports / scripts / docs
- No production import references root `app/` (the 2 legacy importers moved into the
  archive with it).
- No script/doc points to root `app/` as the active backend (root README updated;
  legacy compose/Dockerfile archived).
- Dashboards depend only on the canonical backend (env base URL, default :8100).

## Tests run
- `pytest --collect-only` (whole canonical suite): **885 tests collected, exit 0 —
  zero import errors** after the move (proves no canonical module depended on root
  `app/`).
- Targeted runtime subset (booking tools, evolution/webhook delivery, pricing,
  facility orders, post-confirmation, service resolution): **green** (see run log).
- `ruff check` on canonical: clean.

## Acceptance criteria
1. Canonical backend documented ✅ (ADR + architecture docs)
2. Root `app/` archived ✅ (`legacy/root-app/`)
3. No production script/doc points to `app/` as active backend ✅
4. No dashboard depends on `app/` ✅
5. No duplicate booking/pricing/order/facility path active ✅
6. Legacy LangGraph documented as intentionally discarded ✅
7. Supabase single DB source of truth ✅ (`supabase/migrations/`)
8. Evolution webhook still in canonical ✅ (`api/evolution_webhooks.py`)
9/10. Dashboards unaffected ✅ (no code change; env base URL unchanged)
11. Tests pass (imports verified; targeted subset green) ✅
12. Docs + build report updated ✅

## Known limitations / next steps
- Frontend `typecheck/lint/build` for `apps/admin` + `apps/facility-dashboard` were
  **not** run here (no dashboard files changed; consolidation is backend-only). Run
  them before a dashboard release.
- The full backend suite (~large) was import-verified via collect-only + a targeted
  runtime subset rather than a full end-to-end run in this session.
- Root `.env.example` left in place (legacy-leaning but harmless, not runnable);
  could be pruned later.
- **Deletion** of `legacy/root-app/` was deferred pending owner approval (archived
  first per the task's "prefer archive over deletion" rule). **Update 2026-07-28:**
  owner approved and the archive was subsequently **removed from the tree** — the
  legacy code lives in git history only.
