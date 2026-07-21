# LaundryKhalas WhatsApp Operations Agent

Mock-first backend foundation for the LaundryKhalas WhatsApp Operations
Agent: customer sends a (mock) WhatsApp message -> system stores it -> the
agent handles the happy-path laundry pickup request -> a mock order +
facility assignment is created -> the agent drafts a reply -> an admin
approves/rejects/takes over -> every action is logged.

See `docs/README.md` for the full documentation index, and
`docs/decisions/current-build-decisions.md` for what is and isn't in scope.

## Prerequisites

- Docker + Docker Compose
- (Optional, for running things outside Docker) Python 3.11+

## 1. Install dependencies

Everything runs in Docker, so there's nothing to install locally beyond
Docker itself. If you want a local editable install for your editor's
type-checking:

```bash
pip install -e ".[dev]"
```

## 2. Configure environment

```bash
cp .env.example .env
```

The defaults work as-is for local Docker Compose. Do not put real
Anthropic/OpenAI/Meta credentials in `.env` for this task - live providers
are stubs and intentionally disabled by default.

## 3. Start the stack

```bash
docker compose up --build
```

This starts `postgres` (PostGIS + pgvector + uuid-ossp), `redis`, `api`,
`celery_worker`, and `celery_beat`. The API is available at
`http://localhost:8000`, docs at `http://localhost:8000/docs`.

## 4. Run migrations

```bash
docker compose exec api alembic upgrade head
```

(First time only, or after model changes: generate a new migration with
`docker compose exec api alembic revision --autogenerate -m "message"`.)

## 5. Seed mock data

```bash
docker compose exec api python -m scripts.seed_mock_data
```

Creates two markets (UAE, Qatar), one `CountryConfig` each (mock pricing,
operating hours, policy), and two clearly `[MOCK]`-labeled facilities per
market.

## 6. Run tests

```bash
docker compose exec api pytest
```

## 7. Simulate a mock WhatsApp inbound message

```bash
curl -X POST http://localhost:8000/api/mock-whatsapp/inbound \
  -H "Content-Type: application/json" \
  -d '{
    "market_code": "AE",
    "phone_number": "+971501234567",
    "customer_name": "Jane Doe",
    "message": "I need a wash and fold pickup tomorrow morning near Marina"
  }'
```

The response includes `conversation_id`, `message_id`, and `customer_id`.

## 8. Run the WhatsApp Operations agent

```bash
curl -X POST http://localhost:8000/api/admin/conversations/<conversation_id>/run-agent \
  -H "X-Admin-Api-Key: changeme_local_admin_key"
```

If the message had enough info (service type, area, pickup day/time), this
creates a mock order + facility assignment and drafts a confirmation. If
not, it drafts a follow-up question instead. Either way, the response
includes an `approval_id` - nothing is sent to the customer yet.

## 9. Approve (or reject) the draft reply

```bash
curl -X POST http://localhost:8000/api/admin/approvals/<approval_id>/approve \
  -H "Content-Type: application/json" \
  -H "X-Admin-Api-Key: changeme_local_admin_key" \
  -d '{"decided_by": "founder"}'
```

Approving a `send_customer_reply` action stores a mock outbound message
(`status = mock_sent`) via `GET /api/admin/conversations/<id>/messages`.
Rejecting just records the decision - nothing is sent.

## Everything else via admin APIs

- `GET /api/admin/conversations`, `/{id}`, `/{id}/messages`
- `POST /api/admin/conversations/{id}/manual-takeover` / `/release-takeover`
- `POST /api/admin/conversations/{id}/manual-reply`
- `GET /api/admin/orders`, `/{id}`
- `GET /api/admin/approvals`, `/{id}`
- `GET /api/admin/ai-action-logs`

All admin routes require the `X-Admin-Api-Key` header (see `.env`'s
`ADMIN_API_KEY`) - this is a placeholder auth mechanism for the MVP, not a
real RBAC system (see `docs/checklists/live-whatsapp-readiness.md`).

## What is mock-only in this build

- WhatsApp: `MockWhatsAppAdapter` only. No live Meta Cloud API call exists.
- LLM: `MockProvider` only. Anthropic/OpenAI are stubs that raise
  `NotImplementedError` unless explicitly enabled (they aren't, anywhere in
  this codebase).
- Payments: not implemented at all in this task.
- Facility assignment: naive area-match-or-first-active-facility logic, no
  real routing/capacity optimization.
