"""Assemble the internal Facilities → Overview payload from real fleet metrics.

Pure aggregation over ``facility_overview_repo`` outputs — KPIs, rankings and
service-coverage gaps. No numbers are invented: a metric with no backing data is
returned as ``None`` (rendered as "no data yet" by the UI), never a placeholder
figure (CLAUDE.md §7/§9).
"""
from __future__ import annotations

from db.repositories import catalogue_repo, facility_overview_repo

_TOP_N = 6


def _completion_rate(completed_all: int, total_all: int) -> float | None:
    if not total_all:
        return None
    return round(completed_all / total_all, 4)


def _utilisation_pct(in_progress: int, capacity: int | None) -> float | None:
    if not capacity or capacity <= 0:
        return None
    return round(in_progress / capacity, 4)


def _card(f: dict) -> dict:
    """A facility ranking/snapshot card (safe internal fields only)."""
    return {
        "id": f["id"],
        "name": f["name"],
        "code": f["code"],
        "city": f["city"],
        "area": f["area"],
        "operating_status": f["operating_status"],
        "in_progress": f["in_progress"],
        "completed_period": f["completed_period"],
        "completed_all": f["completed_all"],
        "delayed": f["delayed"],
        "open_issues": f["open_issues"],
        "attention_orders": f["attention_orders"],
        "completion_rate": _completion_rate(f["completed_all"], f["total_all"]),
        "utilisation": _utilisation_pct(f["in_progress"], f["capacity_daily"]),
        "quality_score": f["quality_score"],
    }


def _attention_reasons(f: dict) -> list[str]:
    reasons: list[str] = []
    if f["delayed"] > 0:
        reasons.append(f"{f['delayed']} delayed")
    if f["open_issues"] > 0:
        reasons.append(f"{f['open_issues']} open issue{'s' if f['open_issues'] != 1 else ''}")
    if f["attention_orders"] > 0:
        reasons.append(f"{f['attention_orders']} need action")
    if f["operating_status"] in ("paused", "closed"):
        reasons.append(f["operating_status"])
    if f["capacity_daily"] is None:
        reasons.append("no capacity set")
    return reasons


def _severity(f: dict) -> int:
    score = f["delayed"] * 3 + f["open_issues"] * 2 + f["attention_orders"] * 2
    if f["operating_status"] in ("paused", "closed"):
        score += 1
    return score


async def build_overview(filters: dict) -> dict:
    """filters: {city?, emirate?, status?, service?, days?}. days=None → all-time."""
    facilities = await facility_overview_repo.facility_metrics(filters)
    avg_seconds = await facility_overview_repo.avg_completion_seconds(filters)
    coverage_counts = await facility_overview_repo.service_coverage(filters)
    categories = await catalogue_repo.list_categories()

    # --- KPIs -------------------------------------------------------------
    active_facilities = sum(
        1 for f in facilities
        if f["is_active"] and f["operating_status"] not in ("closed", "paused")
    )
    orders_completed = sum(f["completed_period"] for f in facilities)
    issues_raised = sum(f["issues_period"] for f in facilities)
    pending_actions = sum(f["attention_orders"] + f["open_issues"] for f in facilities)

    utils = [
        _utilisation_pct(f["in_progress"], f["capacity_daily"]) for f in facilities
    ]
    utils = [u for u in utils if u is not None]
    avg_utilisation = round(sum(utils) / len(utils), 4) if utils else None

    kpis = {
        "active_facilities": active_facilities,
        "total_facilities": len(facilities),
        "orders_completed": orders_completed,
        "avg_completion_seconds": None if avg_seconds is None else round(avg_seconds),
        "avg_utilisation": avg_utilisation,
        "issues_raised": issues_raised,
        "pending_actions": pending_actions,
    }

    # --- Rankings ---------------------------------------------------------
    most_active = [
        _card(f) for f in sorted(
            facilities, key=lambda f: (f["in_progress"], f["completed_all"]), reverse=True
        ) if f["in_progress"] > 0
    ][:_TOP_N]

    most_completed = [
        _card(f) for f in sorted(
            facilities, key=lambda f: (f["completed_period"], f["completed_all"]), reverse=True
        ) if f["completed_period"] > 0
    ][:_TOP_N]

    # Standout facility per city (strongest by completed, then quality, then load).
    by_city: dict[str, dict] = {}
    for f in facilities:
        city = f["city"]
        if not city:
            continue
        best = by_city.get(city)
        key = (f["completed_period"], f["quality_score"] or 0, f["in_progress"])
        if best is None or key > best["_key"]:
            by_city[city] = {**_card(f), "city": city, "_key": key}
    standout_by_city = sorted(
        ({k: v for k, v in c.items() if k != "_key"} for c in by_city.values()),
        key=lambda c: c["completed_period"], reverse=True,
    )

    attention = [
        {**_card(f), "reasons": _attention_reasons(f)}
        for f in facilities if _attention_reasons(f)
    ]
    attention.sort(key=lambda c: _severity(
        {"delayed": c["delayed"], "open_issues": c["open_issues"],
         "attention_orders": c["attention_orders"], "operating_status": c["operating_status"]}
    ), reverse=True)
    attention = attention[:_TOP_N]

    # --- Service coverage (all catalogue categories, incl. real zeros = gaps) --
    service_coverage = sorted(
        (
            {
                "service_code": c.get("code"),
                "name": c.get("name"),
                "facility_count": coverage_counts.get(c.get("code"), 0),
            }
            for c in categories
        ),
        key=lambda s: (-s["facility_count"], s["name"] or ""),
    )

    return {
        "kpis": kpis,
        "most_active_facilities": most_active,
        "most_completed_facilities": most_completed,
        "standout_by_city": standout_by_city,
        "attention_facilities": attention,
        "service_coverage": service_coverage,
        "filters_applied": {
            "city": filters.get("city"),
            "emirate": filters.get("emirate"),
            "status": filters.get("status"),
            "service": filters.get("service"),
            "days": filters.get("days"),
        },
    }
