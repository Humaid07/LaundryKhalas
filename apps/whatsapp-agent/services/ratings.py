"""Rating calculation engine — the backend source of truth (spec §7).

Pure functions over ``config/rating_factors.json``: factor definitions, input
validation, the official weighted-overall computation, and history aggregation.
No DB, no network. The API/service layer calls this so the frontend can never
submit an arbitrary official overall that conflicts with the factor scores — the
overall is ALWAYS recomputed here from the (validated) factor scores.

overall = round( sum(score_i * weight_i) / sum(weight_i), rounding_dp ),
clamped to [scale.min, scale.max]. Equal weights collapse to a simple average.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "rating_factors.json"


class RatingValidationError(ValueError):
    """Raised on invalid rating input (surfaced as HTTP 422 by the API layer)."""


@lru_cache(maxsize=1)
def _config() -> dict:
    return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))


def scale() -> tuple[int, int]:
    s = _config().get("scale", {"min": 1, "max": 5})
    return int(s["min"]), int(s["max"])


def _rounding_dp() -> int:
    return int(_config().get("rounding_dp", 1))


def factor_defs(kind: str) -> list[dict]:
    """Canonical factor definitions for 'facility' or 'driver'."""
    key = "facility_factors" if kind == "facility" else "driver_factors"
    return [dict(f) for f in _config().get(key, [])]


def _weight_for(kind: str, factor_key: str) -> float | None:
    for f in factor_defs(kind):
        if f["key"] == factor_key:
            return float(f["weight"])
    return None


def _label_for(kind: str, factor_key: str) -> str | None:
    for f in factor_defs(kind):
        if f["key"] == factor_key:
            return f["label"]
    return None


def validate_and_build_factors(kind: str, factors: list[dict]) -> list[dict]:
    """Validate submitted factor scores and return normalized factor rows with the
    server-side weight + weighted_score attached. Raises RatingValidationError.

    Each input item: {"factor_key": str, "score": number}. Unknown keys are
    rejected; the weight/label come from config (never the client)."""
    lo, hi = scale()
    if not factors:
        raise RatingValidationError("At least one factor score is required.")
    seen: set[str] = set()
    built: list[dict] = []
    for item in factors:
        fkey = (item or {}).get("factor_key")
        if not fkey:
            raise RatingValidationError("Each factor needs a factor_key.")
        weight = _weight_for(kind, fkey)
        if weight is None:
            raise RatingValidationError(f"Unknown {kind} factor: {fkey}")
        if fkey in seen:
            raise RatingValidationError(f"Duplicate factor: {fkey}")
        seen.add(fkey)
        try:
            score = float(item.get("score"))
        except (TypeError, ValueError):
            raise RatingValidationError(f"Factor {fkey} needs a numeric score.")
        if not (lo <= score <= hi):
            raise RatingValidationError(f"Factor {fkey} score must be between {lo} and {hi}.")
        built.append({
            "factor_key": fkey,
            "factor_label": _label_for(kind, fkey) or fkey,
            "score": round(score, 2),
            "weight": weight,
            "weighted_score": round(score * weight, 3),
        })
    return built


def compute_overall(factors: list[dict]) -> float:
    """Official overall = weighted mean of factor scores, rounded + clamped."""
    lo, hi = scale()
    total_weight = sum(float(f["weight"]) for f in factors)
    if total_weight <= 0:
        raise RatingValidationError("Total factor weight must be positive.")
    weighted = sum(float(f["score"]) * float(f["weight"]) for f in factors)
    overall = weighted / total_weight
    overall = max(lo, min(hi, overall))
    return round(overall, _rounding_dp())


def aggregate_summary(evaluations: list[dict]) -> dict:
    """Aggregate a facility's/driver's PUBLISHED evaluation history into a summary.

    ``evaluations`` is a list of {overall_score, evaluation_date, factors:[...]}
    ordered newest-first. Returns current overall (latest), per-factor averages,
    count, latest date, and a chronological trend of overall scores.
    """
    published = [e for e in evaluations if e.get("status", "published") == "published"]
    if not published:
        return {
            "overall_score": None, "evaluation_count": 0,
            "latest_evaluation_date": None, "factor_averages": [], "trend": [],
        }
    dp = _rounding_dp()
    # Newest-first assumed; current = latest published overall.
    current = float(published[0]["overall_score"])
    # Per-factor averages across all published evaluations.
    sums: dict[str, list] = {}
    for e in published:
        for f in e.get("factors", []):
            entry = sums.setdefault(f["factor_key"], [f["factor_label"], 0.0, 0])
            entry[1] += float(f["score"])
            entry[2] += 1
    factor_averages = [
        {"factor_key": k, "factor_label": v[0], "average": round(v[1] / v[2], dp), "count": v[2]}
        for k, v in sums.items()
    ]
    # Trend: chronological (oldest→newest) overall scores.
    trend = [
        {"date": e.get("evaluation_date"), "overall_score": float(e["overall_score"])}
        for e in reversed(published)
    ]
    return {
        "overall_score": round(current, dp),
        "evaluation_count": len(published),
        "latest_evaluation_date": published[0].get("evaluation_date"),
        "factor_averages": factor_averages,
        "trend": trend,
    }
