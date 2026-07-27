"""Facility issue-thread + settings repo tests.

Covers: the facility thread excludes internal-only notes while the internal team
sees them (test 8), and a timing update is a persistent upsert (test 15). SQL is
captured with a stubbed ``database`` since the ``client`` suite runs on SQLite.
"""
from db import database
from db.repositories import (
    facility_issue_messages_repo as msgs,
    facility_issues_repo as issues,
    facility_settings_repo as settings_repo,
)


# --------------------------- issue thread privacy (8) ---------------------
async def test_facility_thread_excludes_internal_notes(monkeypatch):
    captured = {}

    async def fake_fetch(sql, *args):
        captured["sql"] = sql
        return []

    monkeypatch.setattr(database, "fetch", fake_fetch)
    # Facility side: internal-only notes are filtered out.
    await msgs.list_messages("issue-1", include_internal=False)
    assert "is_internal = false" in captured["sql"]


async def test_internal_team_sees_all_notes(monkeypatch):
    captured = {}

    async def fake_fetch(sql, *args):
        captured["sql"] = sql
        return []

    monkeypatch.setattr(database, "fetch", fake_fetch)
    # Internal side: no is_internal FILTER → all messages returned (the column is
    # still selected, but there is no `is_internal = false` predicate).
    await msgs.list_messages("issue-1", include_internal=True)
    assert "is_internal = false" not in captured["sql"]


async def test_internal_reply_is_visible_to_facility(monkeypatch):
    """An internal-team reply that is NOT an internal-only note (is_internal=False)
    is written with sender_type='internal' and therefore surfaces in the facility
    thread (which only hides is_internal=true rows)."""
    captured = {}

    async def fake_fetchrow(sql, *args):
        captured["sql"] = sql
        captured["args"] = args
        return {"id": "m1", "sender_type": args[1], "is_internal": args[5]}

    monkeypatch.setattr(database, "fetchrow", fake_fetchrow)
    out = await msgs.add_message("issue-1", "internal", "We are on it", is_internal=False)
    assert out["sender_type"] == "internal"
    assert out["is_internal"] is False  # visible to the facility thread


async def test_issue_list_scopes_to_facility_when_given(monkeypatch):
    captured = {}

    async def fake_fetch(sql, *args):
        captured["sql"] = sql
        captured["args"] = args
        return []

    monkeypatch.setattr(database, "fetch", fake_fetch)
    await issues.list_issues(facility_id="FAC-1")
    assert "i.facility_id = $1" in captured["sql"]
    assert captured["args"][0] == "FAC-1"
    # Internal listing (facility_id=None) has NO facility filter → no WHERE clause.
    captured.clear()
    await issues.list_issues(facility_id=None)
    assert "where" not in captured["sql"].lower()


# --------------------------- timing persistence (15) ----------------------
async def test_upsert_timing_persists_via_conflict(monkeypatch):
    captured = {}

    async def fake_fetchrow(sql, *args):
        captured["sql"] = sql
        captured["args"] = args
        return {"facility_id": args[0], "day_of_week": args[1]}

    monkeypatch.setattr(database, "fetchrow", fake_fetchrow)
    row = await settings_repo.upsert_timing(
        "FAC-1", 1, opens_at="08:00", closes_at="22:00", is_closed=False)
    assert "on conflict (facility_id, day_of_week) do update" in captured["sql"]
    assert captured["args"][0] == "FAC-1"
    assert captured["args"][1] == 1
    assert row["day_of_week"] == 1


async def test_get_prices_uses_shared_catalogue(monkeypatch):
    async def fake_list_items(category_code=None):
        return [{"item_code": "SHIRT", "canonical_name": "Shirt", "category_name": "Everyday",
                 "pricing_unit": "item", "current_price": 10, "currency": "AED",
                 "is_starting_price": False}]

    monkeypatch.setattr(settings_repo.catalogue_repo, "list_items", fake_list_items)
    out = await settings_repo.get_prices("FAC-1")
    assert out["items"][0]["item_code"] == "SHIRT"
    assert out["items"][0]["current_price"] == 10
    # A note makes clear the facility-specific payable rate is not set yet.
    assert "not configured yet" in out["note"]
