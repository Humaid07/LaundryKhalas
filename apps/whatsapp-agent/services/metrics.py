"""Quality-metrics assembly (pure, deterministic).

Turns raw counts (gathered by ``db/repositories/metrics_repo.py``) into a
structured quality report with safe rates. All ratio math is divide-by-zero safe
and pure, so it's unit-testable without a database. B2B leads are excluded from
consumer conversion upstream (the repo filters them); this layer just assembles.

Do not optimise for shorter conversations — correctness/conversion/trust matter
more (spec). These metrics evaluate future prompt/model changes, not reward speed.
"""
from __future__ import annotations


def ratio(numerator, denominator) -> float:
    """Fraction 0.0–1.0, rounded to 4dp. 0.0 when the denominator is 0."""
    n = float(numerator or 0)
    d = float(denominator or 0)
    return round(n / d, 4) if d else 0.0


def pct(numerator, denominator) -> float:
    """Percentage 0.0–100.0, rounded to 1dp. 0.0 when the denominator is 0."""
    return round(ratio(numerator, denominator) * 100, 1)


def build_quality_report(raw: dict) -> dict:
    """Assemble the quality report from raw counts. ``raw`` keys (all optional,
    default 0) are the consumer/escalation counts + the by-dimension breakdowns.
    Consumer figures EXCLUDE B2B leads (filtered in the repo)."""
    c = raw.get("consumer", {})
    # Counts come back as ints; SQL sum()/revenue can be Decimal — coerce so the
    # arithmetic below never mixes float/Decimal.
    total_customers = int(c.get("total_customers", 0) or 0)
    with_confirmed = int(c.get("customers_with_confirmed", 0) or 0)
    repeat = int(c.get("repeat_customers", 0) or 0)
    booking_started = int(c.get("booking_started", 0) or 0)
    confirmed_orders = int(c.get("confirmed_orders", 0) or 0)
    price_enquiry = int(c.get("price_enquiry_customers", 0) or 0)
    lifetime_value = float(c.get("confirmed_revenue", 0.0) or 0)

    esc = raw.get("escalations", {})
    total_convos = esc.get("total_conversations", 0)
    flagged = esc.get("flagged_conversations", 0)

    return {
        "consumer": {
            "total_customers": total_customers,
            "customers_with_confirmed_order": with_confirmed,
            "repeat_customers": repeat,
            "repeat_customer_rate_pct": pct(repeat, with_confirmed),
            "confirmed_orders": confirmed_orders,
            "confirmed_revenue_aed": round(float(lifetime_value or 0), 2),
            "avg_order_value_aed": round(float(lifetime_value or 0) / confirmed_orders, 2)
            if confirmed_orders else 0.0,
            "conversion": {
                "price_enquiry_customers": price_enquiry,
                "booking_started": booking_started,
                "confirmed": confirmed_orders,
                "started_to_confirmed_rate_pct": pct(confirmed_orders, booking_started),
                "customer_conversion_rate_pct": pct(with_confirmed, total_customers),
            },
        },
        "escalations": {
            "total_conversations": total_convos,
            "flagged_conversations": flagged,
            "escalation_rate_pct": pct(flagged, total_convos),
            "open_complaints": esc.get("open_complaints", 0),
            "pending_tasks_open": esc.get("pending_tasks_open", 0),
            "pending_tasks_overdue": esc.get("pending_tasks_overdue", 0),
        },
        "b2b": {"open_leads": raw.get("b2b", {}).get("open_leads", 0)},
        "by_service": raw.get("by_service", []),
        "by_market": raw.get("by_market", []),
        "by_segment": raw.get("by_segment", []),
    }
