# Repo Structure

**Canonical backend:** `apps/whatsapp-agent/`. See
[`ADR-canonical-backend-runtime`](../decisions/ADR-canonical-backend-runtime.md).

```
LaundryKhalas/
├── apps/
│   ├── whatsapp-agent/      # ★ CANONICAL FastAPI backend / runtime (port 8100)
│   │   ├── main.py          #   app entrypoint (uvicorn main:app)
│   │   ├── api/             #   routes: evolution_webhooks, orders, conversations,
│   │   │                    #   facility, internal_metrics, users, health, …
│   │   ├── agents/whatsapp_agent/  # Claude tool-use booking orchestration
│   │   ├── services/        #   booking_flow, pricing, discount, money,
│   │   │                    #   facility_routing, facility_notifications,
│   │   │                    #   post_confirmation, service_resolution, turn_service, …
│   │   ├── channels/        #   evolution_whatsapp adapter
│   │   ├── db/repositories/ #   asyncpg Supabase repositories (single DB access layer)
│   │   ├── laundry_class/   #   self-contained LangGraph agent
│   │   ├── config/          #   catalogue, services, discounts, SLA (source data)
│   │   ├── tests/           #   backend tests (700+)
│   │   └── pyproject.toml   #   canonical deps + its own .venv
│   ├── admin/               # Internal LaundryKhalas dashboard (Next.js, port 3005)
│   │                        #   → calls the canonical backend (env NEXT_PUBLIC_API_BASE_URL)
│   └── facility-dashboard/  # Partner/facility dashboard (Next.js, port 3010)
│                            #   → calls the canonical backend (no direct Supabase)
├── supabase/
│   └── migrations/          # ★ SINGLE DB source of truth (000001–000028, asyncpg-applied)
├── docs/                    # audits, decisions (ADRs), architecture, build-reports, …
├── legacy/
│   └── root-app/            # ⛔ ARCHIVED legacy prototype backend — reference only
│                            #   (old app/, alembic/, docker-compose.yml, Dockerfile,
│                            #    pyproject.toml, scripts/) — do NOT run or edit
├── CLAUDE.md                # project engineering rules
└── README.md               # points at the canonical backend
```

## Rules
- One backend runtime: `apps/whatsapp-agent/`. Do not create a third backend.
- Dashboards call the canonical backend only (env-controlled base URL); the facility
  dashboard never accesses Supabase directly.
- DB changes go through `supabase/migrations/` (applied via asyncpg — no generic
  runner; apply `.sql` manually).
- `legacy/root-app/` is frozen reference; never add logic there.
