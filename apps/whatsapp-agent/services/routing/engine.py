"""DB-backed routing orchestration: build the request from an order, load the
environment-isolated candidates, and run the shared pure evaluator.

This is the thin adapter around the pure engine (services/routing/evaluator.py) —
it is the SAME evaluation for production orders, synthetic test orders, and the
simulator. Persistence + mode dispatch live in services/facility_routing.py.
"""
from __future__ import annotations

from datetime import datetime

from services.routing import candidate_loader, evaluator
from services.routing.config import ROUTING_VERSION


def _pickup_when(order_row: dict) -> datetime:
    """Requested pickup datetime from the order, else now (naive local)."""
    d = order_row.get("pickup_date")
    t = order_row.get("pickup_start_time")
    try:
        if d is not None and t is not None:
            ds = str(d)
            ts = str(t)
            return datetime.fromisoformat(f"{ds}T{ts}" if "T" not in ds else ds)
    except (ValueError, TypeError):
        pass
    return datetime.now()


def build_request(order_row: dict) -> dict:
    """Grounded routing request from an order row (no invented fields)."""
    priority = "express" if order_row.get("is_express") or order_row.get("express_selected") else "standard"
    return {
        "service_code": (order_row.get("routing_service_code") or order_row.get("service_code")
                         or order_row.get("service")),
        "service_subtype": order_row.get("service_subtype"),
        "required_capabilities": list(order_row.get("required_capabilities") or []),
        "lat": order_row.get("pickup_latitude"),
        "lon": order_row.get("pickup_longitude"),
        "area": order_row.get("pickup_area") or order_row.get("area"),
        "city": order_row.get("city"),
        "emirate": order_row.get("pickup_emirate") or order_row.get("emirate"),
        "market": order_row.get("market"),
        "priority": priority,
        "required_turnaround_hours": order_row.get("required_turnaround_hours"),
        "pickup_at": (str(order_row["pickup_date"]) if order_row.get("pickup_date") else None),
        "is_test": bool(order_row.get("is_test_data")),
    }


async def route_order(order_row: dict, *, when: datetime | None = None, cost_approved: bool = False) -> dict:
    """Evaluate the best facility for an order using the shared engine. Returns
    ``{result, request, when, is_test}``. Environment isolation is enforced by the
    candidate loader (test orders see only test facilities/drivers)."""
    request = build_request(order_row)
    is_test = request["is_test"]
    eval_when = when or _pickup_when(order_row)
    candidates = await candidate_loader.load_candidates(is_test=is_test, market=request.get("market"))
    result = evaluator.evaluate(candidates, request, eval_when, cost_approved=cost_approved)
    return {"result": result, "request": request, "when": eval_when, "is_test": is_test,
            "routing_version": ROUTING_VERSION}
