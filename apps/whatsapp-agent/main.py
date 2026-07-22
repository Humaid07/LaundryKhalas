from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import (
    chat,
    conversations,
    evolution_webhooks,
    flags,
    health,
    orders,
    seo_agents,
    settings_route,
    tickets,
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

    # In local SQLite mode: create the ORM tables and seed the demo orders
    # (LK-AE-1024..1027) so tracking/cancel/change flows and the dashboard have
    # data on a fresh database. Idempotent.
    #
    # In dev/test Supabase mode: the schema AND seed are owned by the SQL
    # migrations + the guarded seed script, so we must NOT run the SQLite ORM
    # create_all/seed against Postgres (it would clash with the managed schema).
    if not database.is_supabase_mode():
        await init_db()
        async with AsyncSessionLocal() as session:
            await order_store.seed_demo_orders(session)
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

app.include_router(chat.router)
app.include_router(orders.router)
app.include_router(conversations.router)
app.include_router(flags.router)
app.include_router(tickets.router)
app.include_router(settings_route.router)
app.include_router(webhooks.router)
app.include_router(evolution_webhooks.router)
app.include_router(seo_agents.router)
app.include_router(health.router)


@app.get("/health")
async def health_root():
    return {"status": "ok"}
