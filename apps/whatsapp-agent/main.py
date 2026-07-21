from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import chat, orders, settings_route, webhooks
from db import AsyncSessionLocal, init_db
from services import order_store
from settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    # Seed the demo orders (LK-AE-1024..1027) so tracking/cancel/change flows
    # and the dashboard have realistic data on a fresh database. Idempotent.
    async with AsyncSessionLocal() as session:
        await order_store.seed_demo_orders(session)
    yield


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
app.include_router(settings_route.router)
app.include_router(webhooks.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
