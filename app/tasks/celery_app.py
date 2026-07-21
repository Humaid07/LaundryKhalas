"""Celery app.

No scheduled/background tasks are required for the MVP happy-path flow
(the agent runs synchronously via the admin run-agent endpoint), but the
worker/beat processes are wired up per the required local dev topology so
future async work (e.g. cost-ceiling resets, scheduled follow-ups) has a
home without re-plumbing docker-compose.
"""
from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "laundrykhalas",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)


@celery_app.task(name="laundrykhalas.ping")
def ping() -> str:
    return "pong"
