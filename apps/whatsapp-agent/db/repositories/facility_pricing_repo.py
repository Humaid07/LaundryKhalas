"""Facility rate-aware quoting (Supabase dev/test schema).

``quote_for_service`` implements the better-rate selection: qualified nearby
facilities that OFFER the service (active, accepts_orders, market match) → lowest
internal rate (distance tie-break) → active margin rule → customer price. Returns
ONLY the customer-facing quote; facility cost + margin never leave this layer.
"""
from __future__ import annotations

from db import database
from services import facility_pricing


async def get_margin_rule(*, bespoke: bool = False, service_code: str | None = None) -> dict | None:
    """Highest-priority active margin rule for the scope. Bespoke > service-specific
    > default. Falls back to the default rule."""
    row = await database.fetchrow(
        """
        select code, scope, service_code, margin_type, margin_value, priority
        from margin_rules
        where active = true and (
              ($1 and scope = 'bespoke')
           or (scope = 'service' and service_code = $2)
           or scope = 'default')
        order by
          (case when $1 and scope = 'bespoke' then 3
                when scope = 'service' and service_code = $2 then 2
                else 1 end) desc,
          priority desc
        limit 1
        """,
        bespoke, service_code,
    )
    return dict(row) if row else None


async def candidates_for_service(service_code: str, *, market: str | None = None,
                                 lat=None, lon=None) -> list[dict]:
    """Qualified facilities offering the service, with their rate + distance."""
    rows = await database.fetch(
        """
        select f.id as facility_id, f.code as facility_code,
               f.latitude, f.longitude, f.capacity_daily,
               r.rate, r.currency
        from facilities f
        join facility_services fs on fs.facility_id = f.id
             and fs.service_code = $1 and fs.offered = true
        join facility_rates r on r.facility_id = f.id
             and r.service_code = $1 and r.active = true
        where f.is_active = true and f.accepts_orders = true
          and f.operating_status not in ('closed','paused')
          and ($2::text is null or f.market is null or f.market = $2::text)
        """,
        service_code, market,
    )
    out = []
    for row in rows:
        d = dict(row)
        d["distance_km"] = facility_pricing.haversine_km(lat, lon, d["latitude"], d["longitude"])
        d["facility_id"] = str(d["facility_id"])
        out.append(d)
    return out


async def quote_for_service(service_code: str, *, market: str | None = None,
                            lat=None, lon=None, bespoke: bool = False) -> dict | None:
    """Full better-rate quote: lowest qualified rate + margin → customer price.
    Returns the customer-safe quote (no cost/margin) or None when no facility
    qualifies (caller then falls back to the standard published price)."""
    candidates = await candidates_for_service(service_code, market=market, lat=lat, lon=lon)
    chosen = facility_pricing.pick_lowest(candidates)
    if not chosen:
        return None
    rule = await get_margin_rule(bespoke=bespoke, service_code=service_code) or {
        "margin_type": "percentage", "margin_value": 0}
    return facility_pricing.customer_quote(chosen, rule)
