"""Quality Check toggle removal (spec §1 / §14).

The partner-facing Settings → Operations "Quality check step" toggle is removed.
These tests lock in that:
  * the settings repo no longer accepts/persists `quality_check_required`;
  * a client that still sends the field has it silently dropped (not written);
  * unrelated operations settings (accepting_orders, daily_capacity, handoff
    window) continue to round-trip.
The order-level QC workflow and the internal `quality_score` rating are separate
systems and are intentionally NOT touched here.
"""
from db.repositories import facility_settings_repo as repo


def test_quality_check_not_in_allow_list():
    assert "quality_check_required" not in repo._SETTINGS_FIELDS
    assert "quality_check" not in " ".join(repo._SETTINGS_FIELDS)


def test_quality_check_not_in_selected_columns():
    assert "quality_check_required" not in repo._SETTINGS_COLS


def test_unrelated_operations_fields_still_supported():
    for field in ("accepting_orders", "daily_capacity", "preferred_handoff_window"):
        assert field in repo._SETTINGS_FIELDS


async def test_update_settings_drops_quality_check_field(monkeypatch):
    """A payload carrying the removed field must not reach the SQL write."""
    captured: dict = {}

    async def fake_get(_fid):
        # Pretend a row already exists so update_settings takes the UPDATE path.
        return {"facility_id": _fid, "accepting_orders": True}

    async def fake_fetchrow(sql, *params):
        captured["sql"] = sql
        captured["params"] = params
        return {"facility_id": params[0]}

    monkeypatch.setattr(repo, "get_settings", fake_get)
    monkeypatch.setattr(repo.database, "fetchrow", fake_fetchrow)

    await repo.update_settings(
        "fac-1", accepting_orders=False, quality_check_required=True,
        quality_check_enabled=True,
    )
    # The removed field never appears in the generated SQL; a legit field does.
    assert "quality_check" not in captured["sql"]
    assert "accepting_orders" in captured["sql"]
