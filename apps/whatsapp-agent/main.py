from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fastapi import Depends

from api import (
    admin_pricing,
    auth,
    catalogue,
    chat,
    conversations,
    deps,
    evolution_webhooks,
    facility,
    flags,
    health,
    internal_facility_issues,
    orders,
    public_pricing,
    seo_agents,
    service_taxonomy,
    settings_route,
    tickets,
    users,
    webhooks,
)
from db import AsyncSessionLocal, database, init_db
from services import order_store
from settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fail fast on a misconfigured WhatsApp provider: the ACTIVE mode's required
    # vars must be present. mock needs nothing; evolution/meta require only their
    # own vars (blank Meta keys never block evolution/mock, and vice versa).
    get_settings().validate_whatsapp_config()
    # Fail fast on a misconfigured Anthropic integration (enabled but no key,
    # empty model, invalid token/timeout config). Never reveals the key. Mock /
    # OpenAI providers never raise here.
    get_settings().validate_ai_config()
    # Fail fast on an unusable LIVE facility-notification config (mock never raises).
    get_settings().validate_facility_notifications_config()

    # In local SQLite mode: create the ORM tables and seed the demo orders
    # (LK-AE-1024..1027) so tracking/cancel/change flows and the dashboard have
    # data on a fresh database. Idempotent.
    #
    # In dev/test Supabase mode: the schema AND seed are owned by the SQL
    # migrations + the guarded seed script, so we must NOT run the SQLite ORM
    # create_all/seed against Postgres (it would clash with the managed schema).
    if not database.is_supabase_mode():
        await init_db()
        # Demo orders auto-seed ONLY when ENABLE_DEMO_DATA=true (local dev). In
        # staging/production this is false, so no fake orders are recreated on
        # startup (spec §2/§23). Supabase mode never auto-seeds either way.
        if get_settings().enable_demo_data:
            async with AsyncSessionLocal() as session:
                await order_store.seed_demo_orders(session)

    # Recover any inbound message turns left buffered / in-flight by a restart so
    # a pending customer message still gets its one reply (spec §§21/27).
    # Supabase-only (the turn model lives there) and best-effort — never blocks
    # startup on error.
    if database.is_supabase_mode() and get_settings().whatsapp_message_aggregation_enabled:
        try:
            from api.evolution_webhooks import recover_pending_turns
            await recover_pending_turns()
        except Exception as exc:  # noqa: BLE001
            import structlog
            structlog.get_logger().warning("turn_recovery_startup_failed", error=str(exc))
    yield
    await database.close_pool()


settings = get_settings()

app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- RBAC guards (gated by REQUIRE_AUTH; anonymous-as-admin in dev) ----------
# Operations + Admin: orders, conversations, flags, tickets (the ops surface).
# Admin only: chat test console, settings, SEO, service taxonomy.
# Never guarded: provider webhooks, /health, /api/auth/* (login must be open).
_OPS = [Depends(deps.require_ops)]
_ADMIN = [Depends(deps.require_admin)]

app.include_router(auth.router)
app.include_router(chat.router, dependencies=_ADMIN)
app.include_router(orders.router, dependencies=_OPS)
app.include_router(conversations.router, dependencies=_OPS)
app.include_router(flags.router, dependencies=_OPS)
app.include_router(tickets.router, dependencies=_OPS)
app.include_router(settings_route.router, dependencies=_ADMIN)
app.include_router(users.router, dependencies=_ADMIN)  # user management (admin only)
app.include_router(webhooks.router)
app.include_router(evolution_webhooks.router)
app.include_router(seo_agents.router, dependencies=_ADMIN)
app.include_router(service_taxonomy.router, dependencies=_ADMIN)
app.include_router(catalogue.router, dependencies=_OPS)
# Admin pricing management — each endpoint self-guards with a specific
# pricing.* permission (services.pricing_permissions), so no router-level guard.
app.include_router(admin_pricing.router)
# Public pricing — UNAUTHENTICATED, read-only, published data only (for the website).
app.include_router(public_pricing.router)
# Facility (partner) dashboard — every endpoint scoped to the caller's facility.
app.include_router(facility.router, dependencies=[Depends(deps.require_facility_scope)])
# Internal ops view of facility-raised issues (operations + admin).
app.include_router(internal_facility_issues.router, dependencies=_OPS)
app.include_router(health.router)


@app.get("/health")
async def health_root():
    return {"status": "ok"}
