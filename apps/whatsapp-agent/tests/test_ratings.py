"""Ratings — calc engine, validation, visibility shaping, ownership, audit.

Invariants (spec §6/§7/§9/§14):
  * overall is computed on the BACKEND from factor scores (weighted mean, 1 dp,
    clamped 1-5); a client cannot submit an arbitrary overall.
  * factor scores must be 1-5; unknown/duplicate factors rejected.
  * PARTNER shape excludes internal_notes, evaluator identity, and weights;
    INTERNAL shape includes them. Partners never see drafts/archived.
  * a partner can only see a driver rating for a driver in their OWN facility.
  * history is preserved (create always inserts a new evaluation).
DB is mocked except where noted.
"""
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from api import facility as facility_api
from db import database
from schemas import EvaluationCreate
from services import ratings, rating_service


# ------------------------------- calc engine -------------------------------
def test_compute_overall_equal_weights_is_average():
    factors = [
        {"factor_key": "a", "score": 4, "weight": 1.0},
        {"factor_key": "b", "score": 5, "weight": 1.0},
    ]
    assert ratings.compute_overall(factors) == 4.5


def test_compute_overall_weighted_and_rounded():
    factors = [
        {"factor_key": "a", "score": 5, "weight": 3.0},
        {"factor_key": "b", "score": 2, "weight": 1.0},
    ]
    # (15 + 2) / 4 = 4.25 -> 4.2 (banker's? Python round(4.25,1)=4.2)
    assert ratings.compute_overall(factors) == round(17 / 4, 1)


def test_compute_overall_clamped_to_scale():
    factors = [{"factor_key": "a", "score": 5, "weight": 1.0}]
    assert ratings.compute_overall(factors) == 5.0


def test_validate_builds_weighted_scores_from_config():
    built = ratings.validate_and_build_factors(
        "facility", [{"factor_key": "service_quality", "score": 4}])
    assert built[0]["weight"] == 1.0
    assert built[0]["weighted_score"] == 4.0
    assert built[0]["factor_label"] == "Service quality"


@pytest.mark.parametrize("bad", [
    [{"factor_key": "unknown_factor", "score": 3}],   # unknown key
    [{"factor_key": "service_quality", "score": 9}],  # out of range
    [{"factor_key": "service_quality", "score": 0}],  # out of range
    [],                                                # empty
    [{"factor_key": "service_quality", "score": 4},
     {"factor_key": "service_quality", "score": 3}],  # duplicate
])
def test_validate_rejects_bad_factor_input(bad):
    with pytest.raises(ratings.RatingValidationError):
        ratings.validate_and_build_factors("facility", bad)


def test_driver_factors_are_distinct_from_facility():
    with pytest.raises(ratings.RatingValidationError):
        # a facility factor key is not a valid driver factor
        ratings.validate_and_build_factors("driver", [{"factor_key": "complaint_rate", "score": 4}])
    ok = ratings.validate_and_build_factors("driver", [{"factor_key": "pickup_punctuality", "score": 4}])
    assert ok[0]["factor_key"] == "pickup_punctuality"


# ------------------------------- aggregation -------------------------------
def test_aggregate_summary_current_averages_and_trend():
    evals = [
        {"overall_score": 4.5, "evaluation_date": "2026-08-01", "status": "published",
         "factors": [{"factor_key": "a", "factor_label": "A", "score": 5}]},
        {"overall_score": 4.0, "evaluation_date": "2026-07-01", "status": "published",
         "factors": [{"factor_key": "a", "factor_label": "A", "score": 3}]},
    ]
    s = ratings.aggregate_summary(evals)
    assert s["overall_score"] == 4.5           # latest (newest-first)
    assert s["evaluation_count"] == 2
    assert s["latest_evaluation_date"] == "2026-08-01"
    assert s["factor_averages"][0]["average"] == 4.0   # (5+3)/2
    assert [t["overall_score"] for t in s["trend"]] == [4.0, 4.5]  # chronological


def test_aggregate_summary_empty_and_ignores_drafts():
    assert ratings.aggregate_summary([])["overall_score"] is None
    only_draft = [{"overall_score": 3.0, "status": "draft", "factors": []}]
    assert ratings.aggregate_summary(only_draft)["evaluation_count"] == 0


# ------------------------------- visibility shaping ------------------------
_ROW = {
    "id": "ev-1", "facility_id": "fac-1", "overall_score": 4.3,
    "partner_visible_summary": "Strong turnaround; improve packaging.",
    "internal_notes": "SECRET — disciplinary discussion pending.",
    "status": "published", "created_by_user_id": "u-admin",
    "updated_by_user_id": "u-admin", "evaluation_date": "2026-08-01",
    "evaluation_period_start": None, "evaluation_period_end": None,
    "created_at": "t", "updated_at": "t",
    "factors": [{"factor_key": "service_quality", "factor_label": "Service quality",
                 "score": 4.0, "weight": 1.0, "weighted_score": 4.0}],
}


def test_partner_shape_hides_internal_notes_and_evaluator_and_weights():
    p = rating_service.to_partner(_ROW)
    flat = str(p)
    assert "SECRET" not in flat
    assert "internal_notes" not in p
    assert "created_by_user_id" not in p
    assert "weight" not in str(p["factors"])
    assert p["partner_visible_summary"] == "Strong turnaround; improve packaging."
    assert p["overall_score"] == 4.3


def test_internal_shape_includes_everything():
    i = rating_service.to_internal(_ROW)
    assert i["internal_notes"].startswith("SECRET")
    assert i["created_by_user_id"] == "u-admin"
    assert i["factors"][0]["weight"] == 1.0


# ------------------------------- backend authority -------------------------
def test_schema_rejects_client_submitted_overall():
    # EvaluationCreate has extra="forbid" and no overall field — a client cannot
    # smuggle an official overall score past the API.
    with pytest.raises(ValidationError):
        EvaluationCreate(factors=[{"factor_key": "service_quality", "score": 4}], overall_score=5)


async def test_create_facility_evaluation_computes_overall_and_audits(monkeypatch):
    created = {}
    audits = []

    async def fake_create(facility_id, *, overall_score, factors, **kw):
        created["overall"] = overall_score
        created["factors"] = factors
        return {"id": "ev-9", "facility_id": facility_id, "overall_score": overall_score,
                "status": "published", "factors": factors, "created_at": "t", "updated_at": "t",
                "evaluation_date": "2026-08-01", "internal_notes": None,
                "partner_visible_summary": None, "created_by_user_id": kw.get("created_by_user_id"),
                "updated_by_user_id": None, "evaluation_period_start": None,
                "evaluation_period_end": None}

    async def fake_audit(**kw):
        audits.append(kw)

    monkeypatch.setattr(rating_service.facility_evaluations_repo, "create", fake_create)
    monkeypatch.setattr(rating_service.facility_audit_repo, "create", fake_audit)

    out = await rating_service.create_facility_evaluation(
        "fac-1",
        {"factors": [{"factor_key": "service_quality", "score": 4},
                     {"factor_key": "order_accuracy", "score": 5}]},
        actor_id="u1", source_app="admin_dashboard")
    assert created["overall"] == 4.5            # backend-computed
    assert out["overall_score"] == 4.5
    assert audits[0]["action"] == "facility_rating_created"
    assert audits[0]["after"]["entity_type"] == "facility"


# ------------------------------- partner ownership -------------------------
async def test_partner_cannot_view_unrelated_driver_rating(monkeypatch):
    monkeypatch.setattr(database, "is_supabase_mode", lambda: True)

    async def fake_get(_fid, _did):
        return None  # driver not in this facility

    monkeypatch.setattr(facility_api.facility_drivers_repo, "get", fake_get)
    principal = {"facility_id": "mine", "role": "facility_owner", "id": "u1"}
    with pytest.raises(HTTPException) as exc:
        await facility_api.facility_driver_rating("other-facility-driver", principal)
    assert exc.value.status_code == 404
