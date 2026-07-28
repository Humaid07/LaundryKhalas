from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import admin, approvals, conversations, health, messages, mock_whatsapp, orders
from app.core.config import get_settings
from app.core.logging import configure_logging

settings = get_settings()
configure_logging(debug=settings.app_debug)

app = FastAPI(title=settings.app_name, debug=settings.app_debug)

# Narrow allow-list (admin UI dev server only) - never a wildcard, since
# admin routes carry an API key header and customer data.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins_list,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Admin-Api-Key"],
)

app.include_router(health.router)
app.include_router(mock_whatsapp.router, prefix=settings.api_prefix)
app.include_router(conversations.router, prefix=settings.api_prefix)
app.include_router(messages.router, prefix=settings.api_prefix)
app.include_router(orders.router, prefix=settings.api_prefix)
app.include_router(approvals.router, prefix=settings.api_prefix)
app.include_router(admin.router, prefix=settings.api_prefix)
