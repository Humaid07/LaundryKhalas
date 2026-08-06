"""Ranking score for ELIGIBLE facilities (pure, documented weights).

The legacy production router uses no rating; facility_matching uses raw
quality_score. The advanced engine introduces an explicit, DOCUMENTED Bayesian
weighted rating so a 4.9-with-3-reviews facility does not outrank a
4.7-with-160-reviews one, plus normalised components for distance, quality,
workload, driver availability and pickup delay. Internal cost is included ONLY if
it is an approved routing factor (default: not approved -> weight 0).

Every component is in [0,1]; the final score is their weighted sum. Weights are a
module constant so ranking is explicit and testable.
"""

from __future__ import annotations

# Bayesian prior: global mean rating + confidence (reviews needed to trust it).
BAYES_PRIOR_MEAN = 4.3
BAYES_CONFIDENCE = 20.0

# Distance beyond which the distance component is 0 (km).
DISTANCE_HORIZON_KM = 15.0

# Component weights (sum≈1.0; cost is 0 unless internal cost is approved).
WEIGHTS = {
    "distance": 0.30,
    "weighted_rating": 0.25,
    "quality": 0.10,
    "workload": 0.15,
    "available_drivers": 0.10,
    "pickup_delay": 0.10,
    "cost": 0.0,
}


def weighted_rating(rating, review_count, *, prior_mean=BAYES_PRIOR_MEAN, confidence=BAYES_CONFIDENCE) -> float:
    """Bayesian-smoothed rating in [0,5]. Few reviews pull toward the prior mean."""
    r = float(rating) if rating is not None else prior_mean
    n = float(review_count or 0)
    return (confidence * prior_mean + n * r) / (confidence + n)


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def score_candidate(
    eligibility: dict,
    candidate: dict,
    *,
    pickup_delay_minutes: float | None = None,
    cost_approved: bool = False,
) -> dict:
    """Compute score components + final score for one ELIGIBLE candidate."""
    dist = eligibility.get("distance_km")
    distance_c = 1.0 if dist is None else _clamp01(1.0 - float(dist) / DISTANCE_HORIZON_KM)

    wr = weighted_rating(candidate.get("rating"), candidate.get("review_count"))
    rating_c = _clamp01(wr / 5.0)

    quality = candidate.get("quality_score")
    quality_c = _clamp01(float(quality) / 100.0) if quality is not None else 0.5

    # Workload: prefer more remaining capacity.
    wl = candidate.get("current_workload_pct")
    if wl is not None:
        workload_c = _clamp01(1.0 - float(wl) / 100.0)
    else:
        cap = candidate.get("max_concurrent_orders") or candidate.get("capacity_daily")
        if cap:
            used = float(candidate.get("active_load", 0) or 0) / float(cap)
            workload_c = _clamp01(1.0 - used)
        else:
            workload_c = 0.7  # unknown capacity -> neutral-ish

    avail = (eligibility.get("driver_summary") or {}).get("available", 0)
    drivers_c = _clamp01(min(int(avail), 3) / 3.0)

    if pickup_delay_minutes is None:
        pickup_c = 1.0
    else:
        pickup_c = _clamp01(1.0 - float(pickup_delay_minutes) / 240.0)  # 4h horizon

    cost_c = 0.0  # placeholder; only meaningful when cost_approved

    weights = dict(WEIGHTS)
    if not cost_approved:
        weights["cost"] = 0.0

    components = {
        "distance": round(distance_c, 4),
        "weighted_rating": round(rating_c, 4),
        "quality": round(quality_c, 4),
        "workload": round(workload_c, 4),
        "available_drivers": round(drivers_c, 4),
        "pickup_delay": round(pickup_c, 4),
        "cost": round(cost_c, 4),
    }
    final = sum(components[k] * weights[k] for k in components)

    return {
        "score": round(final, 6),
        "components": components,
        "weights": weights,
        "weighted_rating_value": round(wr, 4),
        "raw_rating": candidate.get("rating"),
        "review_count": candidate.get("review_count"),
        "quality_score": candidate.get("quality_score"),
    }
