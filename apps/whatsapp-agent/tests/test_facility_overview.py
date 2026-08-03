"""Internal Facilities → Overview: fleet-metric assembly, repo SQL scoping, and
the endpoint's non-supabase guard.

Follows the repo convention: DB paths are exercised by capturing the SQL/args
(asserting facility scoping + period param) rather than hitting Postgres, and the
assembly logic is tested against canned repo outputs.
"""
import pytest

from api import internal_facilities
from db import database
from db.repositories import catalogue_repo, facility_overview_repo
from services import facility_overview as svc


def _fac(**over):
    base = dict(
        id="f", name="F", code="FAC-F", city="Dubai", area="Al Barsha", emirate="Dubai",
        operating_status="open", is_active=True, capacity_daily=10, quality_score=90.0,
        in_progress=0, attention_orders=0, delayed=0, completed_period=0,
        completed_all=0, total_all=0, open_issues=0, issues_period=0,
    )
    base.update(over)
    return base


FACS = [
    _fac(id="1", name="Bright Wash", city="Dubai", in_progress=5, completed_period=10,
         completed_all=20, total_all=25, capacity_daily=10, quality_score=90.0,
         delayed=1, issues_period=1),
    _fac(id="2", name="Crystal Clean", city="Dubai", in_progress=2, completed_period=15,
         completed_all=30, total_all=40, capacity_daily=None, quality_score=80.0,
         open_issues=2, attention_orders=1, issues_period=3),
    _fac(id="3", name="Capital Cleaners", city="Abu Dhabi", emirate="Abu Dhabi",
         operating_status="paused", in_progress=8, completed_period=5, completed_all=5,
         total_all=10, capacity_daily=20, quality_score=70.0),
]


async def _build(monkeypatch, *, avg=3600.0, coverage=None, cats=None):
    coverage = coverage if coverage is not None else {"WASH_FOLD": 2}
    cats = cats if cats is not None else [
        {"code": "WASH_FOLD", "name": "Wash & Fold"},
        {"code": "ALTERATIONS", "name": "Alterations"},
    ]

    async def fake_metrics(filters):
        return [dict(f) for f in FACS]

    async def fake_avg(filters):
        return avg

    async def fake_cov(filters):
        return dict(coverage)

    async def fake_cats():
        return cats

    monkeypatch.setattr(facility_overview_repo, "facility_metrics", fake_metrics)
    monkeypatch.setattr(facility_overview_repo, "avg_completion_seconds", fake_avg)
    monkeypatch.setattr(facility_overview_repo, "service_coverage", fake_cov)
    monkeypatch.setattr(catalogue_repo, "list_categories", fake_cats)
    return await svc.build_overview({"days": 30})


# ------------------------------- KPIs -------------------------------------
async def test_kpis(monkeypatch):
    out = await _build(monkeypatch)
    k = out["kpis"]
    assert k["active_facilities"] == 2          # paused facility excluded
    assert k["total_facilities"] == 3
    assert k["orders_completed"] == 30          # 10 + 15 + 5 (period)
    assert k["issues_raised"] == 4              # 1 + 3 + 0
    assert k["pending_actions"] == 3            # (0+0)+(1+2)+(0+0)
    assert k["avg_completion_seconds"] == 3600
    # utilisation averaged only over facilities WITH capacity: (5/10 + 8/20)/2
    assert k["avg_utilisation"] == pytest.approx(0.45)


async def test_avg_completion_honest_null(monkeypatch):
    out = await _build(monkeypatch, avg=None)
    assert out["kpis"]["avg_completion_seconds"] is None  # no data → null, not 0


# ----------------------------- rankings -----------------------------------
async def test_rankings(monkeypatch):
    out = await _build(monkeypatch)
    assert [f["name"] for f in out["most_active_facilities"]] == [
        "Capital Cleaners", "Bright Wash", "Crystal Clean"]     # by in_progress desc
    assert [f["name"] for f in out["most_completed_facilities"]] == [
        "Crystal Clean", "Bright Wash", "Capital Cleaners"]     # by completed_period desc
    # completion_rate = completed_all / total_all
    bright = next(f for f in out["most_active_facilities"] if f["name"] == "Bright Wash")
    assert bright["completion_rate"] == pytest.approx(0.8)      # 20/25


async def test_standout_by_city(monkeypatch):
    out = await _build(monkeypatch)
    standout = {c["city"]: c["name"] for c in out["standout_by_city"]}
    assert standout == {"Dubai": "Crystal Clean", "Abu Dhabi": "Capital Cleaners"}


async def test_attention_facilities(monkeypatch):
    out = await _build(monkeypatch)
    names = [f["name"] for f in out["attention_facilities"]]
    assert names[0] == "Crystal Clean"          # highest severity (issues + actions)
    assert "Capital Cleaners" in names          # paused → attention
    crystal = out["attention_facilities"][0]
    assert any("open issue" in r for r in crystal["reasons"])


async def test_service_coverage_includes_gaps(monkeypatch):
    out = await _build(monkeypatch)
    cov = {s["service_code"]: s["facility_count"] for s in out["service_coverage"]}
    assert cov == {"WASH_FOLD": 2, "ALTERATIONS": 0}   # real zero = coverage gap
    assert out["service_coverage"][0]["service_code"] == "WASH_FOLD"  # sorted desc


# ------------------------------- repo SQL ---------------------------------
async def test_facility_metrics_scopes_and_periods(monkeypatch):
    captured = {}

    async def fake_fetch(sql, *args):
        captured["sql"] = sql
        captured["args"] = args
        return []

    monkeypatch.setattr(database, "fetch", fake_fetch)
    await facility_overview_repo.facility_metrics(
        {"city": "Dubai", "status": "open", "days": 30}
    )
    sql = captured["sql"]
    assert "o.facility_id = f.id" in sql
    assert "in_progress" in sql and "completed_period" in sql
    # user filters + period are all parameterised
    assert "Dubai" in captured["args"] and "open" in captured["args"]
    assert 30 in captured["args"]


async def test_avg_completion_returns_none(monkeypatch):
    async def fake_fetchval(sql, *args):
        return None

    monkeypatch.setattr(database, "fetchval", fake_fetchval)
    assert await facility_overview_repo.avg_completion_seconds({"days": None}) is None


async def test_service_coverage_ignores_service_filter(monkeypatch):
    captured = {}

    async def fake_fetch(sql, *args):
        captured["args"] = args
        return []

    monkeypatch.setattr(database, "fetch", fake_fetch)
    await facility_overview_repo.service_coverage(
        {"city": "Dubai", "service": "WASH_FOLD"}
    )
    # 'service' must NOT constrain coverage (we show all services incl. gaps)
    assert "WASH_FOLD" not in captured["args"]
    assert "Dubai" in captured["args"]


# ----------------------------- endpoint guard -----------------------------
async def test_overview_endpoint_empty_when_not_supabase(monkeypatch):
    monkeypatch.setattr(database, "is_supabase_mode", lambda: False)
    out = await internal_facilities.facilities_overview(principal={})
    assert out["kpis"]["orders_completed"] == 0
    assert out["most_active_facilities"] == []
    assert out["filters_applied"]["days"] == 30
