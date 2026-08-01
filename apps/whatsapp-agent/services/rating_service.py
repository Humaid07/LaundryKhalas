"""Ratings orchestration + visibility boundary (spec §5/§7/§9/§10).

Sits between the API and the evaluation repos. Responsibilities:
  * validate factor scores and compute the OFFICIAL overall via services/ratings
    (the client-submitted overall, if any, is ignored — backend is source of truth);
  * write create/update with a facility_audit_log entry (before/after scores + status);
  * shape responses per audience — INTERNAL sees everything (internal_notes,
    evaluator ids, weights, drafts); PARTNER sees only published evaluations with
    the overall, approved factor scores, dates, and the partner-visible summary,
    NEVER internal notes / drafts / archived / evaluator identity (spec §9).

Ownership (facility/driver in scope) is resolved upstream and passed in; this
module never trusts a client id.
"""
from __future__ import annotations

from db.repositories import (
    driver_evaluations_repo,
    facility_audit_repo,
    facility_evaluations_repo,
)
from services import ratings

# ------------------------------------------------------------------ shaping
_HDR_COMMON = ("evaluation_date", "evaluation_period_start", "evaluation_period_end",
               "status", "created_at", "updated_at")


def to_internal(row: dict) -> dict:
    """Full internal representation — nothing hidden."""
    out = {
        "id": str(row["id"]),
        "overall_score": row.get("overall_score"),
        "partner_visible_summary": row.get("partner_visible_summary"),
        "internal_notes": row.get("internal_notes"),
        "created_by_user_id": _s(row.get("created_by_user_id")),
        "updated_by_user_id": _s(row.get("updated_by_user_id")),
        "factors": [
            {"factor_key": f["factor_key"], "factor_label": f["factor_label"],
             "score": f["score"], "weight": f["weight"], "weighted_score": f["weighted_score"]}
            for f in row.get("factors", [])
        ],
    }
    for k in _HDR_COMMON:
        out[k] = _s(row.get(k))
    for id_key in ("facility_id", "driver_id"):
        if id_key in row:
            out[id_key] = _s(row.get(id_key))
    return out


def to_partner(row: dict) -> dict:
    """Partner-safe representation — NO internal_notes, NO evaluator identity, NO
    weight/weighted_score internal calc metadata. Only for PUBLISHED evaluations
    (the caller must filter status)."""
    return {
        "id": str(row["id"]),
        "overall_score": row.get("overall_score"),
        "partner_visible_summary": row.get("partner_visible_summary"),
        "evaluation_date": _s(row.get("evaluation_date")),
        "factors": [
            {"factor_key": f["factor_key"], "factor_label": f["factor_label"],
             "score": f["score"]}
            for f in row.get("factors", [])
        ],
    }


def _s(v):
    return str(v) if v is not None else None


# ------------------------------------------------------------- audit helper
def _audit_values(row: dict | None) -> dict | None:
    if row is None:
        return None
    return {
        "overall_score": row.get("overall_score"),
        "status": row.get("status"),
        "factors": {f["factor_key"]: f["score"] for f in row.get("factors", [])},
    }


async def _audit(*, facility_id, action, entity_type, entity_id, evaluation_id,
                 before, after, actor_id, source_app):
    await facility_audit_repo.create(
        facility_id=facility_id, action=action, actor_id=actor_id,
        actor_type="internal", source_app=source_app,
        before=before, after={
            **(after or {}),
            "entity_type": entity_type, "entity_id": _s(entity_id),
            "evaluation_id": _s(evaluation_id),
        },
    )


# ============================================================ FACILITY
async def create_facility_evaluation(facility_id: str, payload: dict, *,
                                     actor_id: str | None, source_app: str | None = None) -> dict:
    factors = ratings.validate_and_build_factors("facility", payload.get("factors") or [])
    overall = ratings.compute_overall(factors)
    row = await facility_evaluations_repo.create(
        facility_id, overall_score=overall, factors=factors,
        evaluation_date=payload.get("evaluation_date"),
        evaluation_period_start=payload.get("evaluation_period_start"),
        evaluation_period_end=payload.get("evaluation_period_end"),
        partner_visible_summary=payload.get("partner_visible_summary"),
        internal_notes=payload.get("internal_notes"),
        status=payload.get("status") or "published",
        created_by_user_id=actor_id,
    )
    await _audit(facility_id=facility_id, action="facility_rating_created",
                 entity_type="facility", entity_id=facility_id, evaluation_id=row["id"],
                 before=None, after=_audit_values(row), actor_id=actor_id, source_app=source_app)
    return to_internal(row)


async def update_facility_evaluation(facility_id: str, evaluation_id: str, payload: dict, *,
                                     actor_id: str | None, source_app: str | None = None) -> dict | None:
    before = await facility_evaluations_repo.get(evaluation_id, facility_id=facility_id)
    if before is None:
        return None
    kwargs = _update_kwargs("facility", payload)
    row = await facility_evaluations_repo.update(
        evaluation_id, facility_id, updated_by_user_id=actor_id, **kwargs)
    action = ("rating_archived" if payload.get("status") == "archived"
              else "facility_rating_updated")
    await _audit(facility_id=facility_id, action=action,
                 entity_type="facility", entity_id=facility_id, evaluation_id=evaluation_id,
                 before=_audit_values(before), after=_audit_values(row),
                 actor_id=actor_id, source_app=source_app)
    return to_internal(row)


async def facility_summary(facility_id: str) -> dict:
    evals = await facility_evaluations_repo.published_with_factors(facility_id)
    return ratings.aggregate_summary(evals)


async def list_facility_evaluations_internal(facility_id: str, *, status=None,
                                             limit=50, offset=0) -> dict:
    rows = await facility_evaluations_repo.list_for_facility(
        facility_id, status=status, limit=limit, offset=offset)
    total = await facility_evaluations_repo.count_for_facility(facility_id, status=status)
    return {"evaluations": [to_internal(r) for r in rows], "total": total,
            "limit": limit, "offset": offset}


# ============================================================ DRIVER
async def create_driver_evaluation(driver_id: str, payload: dict, *, facility_id: str | None,
                                   actor_id: str | None, source_app: str | None = None) -> dict:
    factors = ratings.validate_and_build_factors("driver", payload.get("factors") or [])
    overall = ratings.compute_overall(factors)
    row = await driver_evaluations_repo.create(
        driver_id, facility_id=facility_id, overall_score=overall, factors=factors,
        evaluation_date=payload.get("evaluation_date"),
        evaluation_period_start=payload.get("evaluation_period_start"),
        evaluation_period_end=payload.get("evaluation_period_end"),
        partner_visible_summary=payload.get("partner_visible_summary"),
        internal_notes=payload.get("internal_notes"),
        status=payload.get("status") or "published",
        created_by_user_id=actor_id,
    )
    await _audit(facility_id=facility_id, action="driver_rating_created",
                 entity_type="driver", entity_id=driver_id, evaluation_id=row["id"],
                 before=None, after=_audit_values(row), actor_id=actor_id, source_app=source_app)
    return to_internal(row)


async def update_driver_evaluation(driver_id: str, evaluation_id: str, payload: dict, *,
                                   actor_id: str | None, source_app: str | None = None) -> dict | None:
    before = await driver_evaluations_repo.get(evaluation_id, driver_id=driver_id)
    if before is None:
        return None
    kwargs = _update_kwargs("driver", payload)
    row = await driver_evaluations_repo.update(
        evaluation_id, driver_id, updated_by_user_id=actor_id, **kwargs)
    action = ("rating_archived" if payload.get("status") == "archived"
              else "driver_rating_updated")
    await _audit(facility_id=before.get("facility_id"), action=action,
                 entity_type="driver", entity_id=driver_id, evaluation_id=evaluation_id,
                 before=_audit_values(before), after=_audit_values(row),
                 actor_id=actor_id, source_app=source_app)
    return to_internal(row)


async def driver_summary(driver_id: str) -> dict:
    evals = await driver_evaluations_repo.published_with_factors(driver_id)
    return ratings.aggregate_summary(evals)


# ------------------------------------------------------------- partner views
async def facility_partner_view(facility_id: str) -> dict:
    """Partner-safe facility rating: aggregate summary + the latest PUBLISHED
    evaluation shaped for the partner (no internal notes / evaluator / drafts)."""
    evals = await facility_evaluations_repo.published_with_factors(facility_id)
    return {
        "summary": ratings.aggregate_summary(evals),
        "latest": to_partner(evals[0]) if evals else None,
    }


async def driver_partner_view(driver_id: str) -> dict:
    evals = await driver_evaluations_repo.published_with_factors(driver_id)
    return {
        "summary": ratings.aggregate_summary(evals),
        "latest": to_partner(evals[0]) if evals else None,
    }


async def list_driver_evaluations_internal(driver_id: str, *, status=None,
                                           limit=50, offset=0) -> dict:
    rows = await driver_evaluations_repo.list_for_driver(
        driver_id, status=status, limit=limit, offset=offset)
    total = await driver_evaluations_repo.count_for_driver(driver_id, status=status)
    return {"evaluations": [to_internal(r) for r in rows], "total": total,
            "limit": limit, "offset": offset}


# ------------------------------------------------------------- shared helper
def _update_kwargs(kind: str, payload: dict) -> dict:
    """Build repo.update kwargs from a partial payload. Factors (if present) are
    re-validated and the overall recomputed on the backend."""
    kwargs: dict = {}
    if "factors" in payload and payload["factors"] is not None:
        factors = ratings.validate_and_build_factors(kind, payload["factors"])
        kwargs["factors"] = factors
        kwargs["overall_score"] = ratings.compute_overall(factors)
    for k in ("evaluation_date", "evaluation_period_start", "evaluation_period_end", "status"):
        if payload.get(k) is not None:
            kwargs[k] = payload[k]
    # summary/notes: allow explicit clearing (present but null) vs untouched (absent)
    if "partner_visible_summary" in payload:
        kwargs["partner_visible_summary"] = payload["partner_visible_summary"]
        kwargs["_set_summary"] = True
    if "internal_notes" in payload:
        kwargs["internal_notes"] = payload["internal_notes"]
        kwargs["_set_notes"] = True
    return kwargs
