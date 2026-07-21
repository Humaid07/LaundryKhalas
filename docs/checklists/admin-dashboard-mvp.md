# Admin Dashboard MVP Checklist

No frontend is built in this task. This checklist tracks what the backend
already exposes for a future React/Next.js admin dashboard to consume, and
what that dashboard needs to show.

## APIs available today

- [x] Conversation inbox: `GET /api/admin/conversations`,
      `GET /api/admin/conversations/{id}`
- [x] Message history per conversation:
      `GET /api/admin/conversations/{id}/messages`
- [x] Manual reply: `POST /api/admin/conversations/{id}/manual-reply`
- [x] Manual takeover toggle:
      `POST /api/admin/conversations/{id}/manual-takeover`,
      `POST /api/admin/conversations/{id}/release-takeover`
- [x] Run the agent on demand:
      `POST /api/admin/conversations/{id}/run-agent`
- [x] Orders list/detail: `GET /api/admin/orders`,
      `GET /api/admin/orders/{id}`
- [x] Approval queue: `GET /api/admin/approvals`,
      `GET /api/admin/approvals/{id}`,
      `POST /api/admin/approvals/{id}/approve`,
      `POST /api/admin/approvals/{id}/reject`
- [x] AI action log: `GET /api/admin/ai-action-logs`
      (optionally filtered by `conversation_id`)

## Not yet available (future work)

- [ ] Pagination/filtering on list endpoints (currently return everything,
      capped only on ai-action-logs via `limit`)
- [ ] Customer detail view / customer search endpoint
- [ ] Facility management endpoints (CRUD)
- [ ] Market/CountryConfig management endpoints (currently seed-only)
- [ ] Cost tracking dashboard endpoint (`CostTracking` table exists, no
      admin route reads it yet)
- [ ] Real auth (see live-whatsapp-readiness.md) - today it's a single
      shared API key, not per-user roles

## UI ideas worth carrying into the future dashboard

(See `docs/audits/fresh-project-start-report.md` §13 for the full
rationale - these were observed in the prototype and are worth keeping as
*ideas*, not code.)

- Conversation inbox: status-tab filtering, searchable list + thread view
- Manual-takeover as a single visible toggle per conversation
- Approval queue as its own first-class surface, urgency-sortable
- AI action log / cost tracking as a visible page, not just background logs
- Order status pipeline shown as a badge-per-state list
