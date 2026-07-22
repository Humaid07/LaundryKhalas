"""Service taxonomy API — serves the canonical LaundryKhalas service catalog
(synced to the live website) and a cross-surface consistency health check.

Read-only. No live external calls. The dashboard reads ``/health`` to show a
"Service taxonomy mismatch detected." warning when a surface drifts.
"""
from __future__ import annotations

from fastapi import APIRouter

from rules import promotional_items, service_catalog, service_promises
from services import service_selection
from services.taxonomy_sync import check_taxonomy_sync

router = APIRouter(prefix="/api/service-taxonomy", tags=["service-taxonomy"])


def _public_service(s: dict) -> dict:
    """Trim a catalog entry to the fields the dashboard/agent need (drops the
    back-compat mirror keys)."""
    sid = s.get("service_id", s.get("key"))
    return {
        "service_id": sid,
        "display_name": s.get("display_name", s.get("label")),
        "category": s.get("category"),
        "unit_type": s.get("unit_type"),
        "starting_price_aed": s.get("starting_price_aed"),
        "description": s.get("description"),
        "eligible_items": s.get("eligible_items", []),
        "market_availability": s.get("market_availability", []),
        "requires_measurement": bool(s.get("requires_measurement")),
        "requires_manual_quote": bool(s.get("requires_manual_quote")),
        "active": bool(s.get("active", True)),
        "source_url": s.get("source_url"),
    }


@router.get("")
async def get_taxonomy():
    """Full canonical catalog + promotional items + service promises."""
    return {
        "services": [_public_service(s) for s in service_catalog()],
        "promotional_items": promotional_items(),
        "service_promises": service_promises(),
    }


@router.get("/options")
async def get_options():
    """The ordered service options the WhatsApp agent shows when asking which
    service the customer needs (includes the 'Not sure / Help me choose' option)."""
    return {"options": service_selection.service_options()}


@router.get("/health")
async def taxonomy_health():
    """Cross-surface consistency report (backend vs WhatsApp vs SEO vs dashboard).
    ``in_sync: false`` drives the dashboard's mismatch warning."""
    return check_taxonomy_sync()
