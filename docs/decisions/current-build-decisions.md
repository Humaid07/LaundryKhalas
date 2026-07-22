# Current Build Decisions

This document records the decisions in force for the current build of the
LaundryKhalas WhatsApp Operations Agent. It supersedes any older/prototype
decisions where they conflict.

- **Fresh project.** This codebase is a clean start, not a continuation of
  `D:\LaundryKhalas\LaundryKhalasPrototype`. See
  `docs/audits/fresh-project-start-report.md` for what was reviewed and why.
- **WhatsApp operations agent is the first business module.** No other
  agent (classifier, SEO, marketing) is built in this task.
- **Classifier agent is deferred to a future task.** Where classification
  would normally be needed (intent, sentiment, urgency), this build uses
  simple deterministic placeholder fields/logic (see
  `Conversation.latest_intent/latest_sentiment/latest_urgency`, and
  `tools.extract_order_slots`) instead of a real classifier.
- **Mock-first only.** No live WhatsApp, Stripe, Anthropic, or OpenAI calls
  anywhere in this codebase. Every external-looking integration point is
  either a Mock adapter/provider or an explicit stub that raises
  `NotImplementedError`.
- **PostgreSQL is the core database**, with `uuid-ossp`, `postgis`, and
  `vector` extensions enabled. No MySQL, no Cloudflare D1 as core DB.
- **FastAPI** is the backend framework, with SQLAlchemy 2.0 async + Alembic
  for migrations, and Pydantic v2 for schemas.
- **Redis/Celery** provide background job infrastructure (worker + beat),
  wired up in docker-compose even though the MVP agent runs synchronously.
- **LangGraph** orchestrates the WhatsApp Operations agent
  (`app/agents/whatsapp_operations/graph.py`) rather than a hand-rolled
  sequential tool chain.
- **MockProvider is the default LLM provider.** Anthropic/OpenAI providers
  are stubs that raise `NotImplementedError`; they are only selectable via
  `LLM_DEFAULT_PROVIDER` + their own `LLM_ENABLE_*` flag, both of which
  default to disabled.
- **Meta WhatsApp Cloud API is the intended future WhatsApp provider.** No
  Respond.io, Wati, or unofficial WhatsApp automation. `MetaWhatsAppStub`
  exists as a placeholder only.
- **Stripe is the intended future payment provider**, mock-first; no
  payment provider is implemented in this task at all.
- **Admin approval is required for every agent-generated customer reply**
  in this MVP - see `HumanApproval` + `/api/admin/approvals/*`. Nothing is
  ever auto-sent.
- **No SEO or marketing agents** in this task.
- **No driver app or customer mobile app** in this task.
- **The prototype folder is reference material only, not source of truth.**
  No prototype code, secrets, or demo data were copied in; concepts
  (mock adapter pattern, approval-gated replies, audit logging, DB-sourced
  pricing) were reused, not the implementations.
