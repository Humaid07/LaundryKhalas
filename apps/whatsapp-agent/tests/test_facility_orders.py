"""Facility order repo + service tests: isolation, bucket→status mapping,
PII-safe serializer, and the facility action allow-list.

Supabase-only DB paths are exercised by capturing the SQL built (asserting the
facility_id filter + bucket status sets) rather than hitting Postgres — the
``client`` suite runs against SQLite.
"""
import pytest

from db import database
from db.repositories import facility_orders_repo as repo
from services import facility_orders as svc


# --------------------------- isolation (1-2) ------------------------------
async def test_get_is_scoped_to_facility(monkeypatch):
    captured = {}

    async def fake_fetchrow(sql, *args):
        captured["sql"] = sql
        captured["args"] = args
        return None  # mismatched facility → no row

    monkeypatch.setattr(database, "fetchrow", fake_fetchrow)
    result = await repo.get("FAC-1", "LK-2026-000004")
    # A mismatched/other facility is indistinguishable from missing → None.
    assert result is None
    assert "o.facility_id = $1" in captured["sql"]
    assert captured["args"][0] == "FAC-1"  # always scoped by the principal's facility


async def test_list_bucket_always_filters_facility_id(monkeypatch):
    captured = {}

    async def fake_fetch(sql, *args):
        captured["sql"] = sql
        captured["args"] = args
        return []

    monkeypatch.setattr(database, "fetch", fake_fetch)
    await repo.list_bucket("FAC-XYZ", "in")
    assert "o.facility_id = $1" in captured["sql"]
    assert captured["args"][0] == "FAC-XYZ"


# --------------------------- bucket mapping (3-5) -------------------------
def test_bucket_status_sets_exact():
    assert repo.BUCKET_STATUSES["in"] == ("active", "pickup_scheduled", "picked_up", "in_cleaning")
    assert repo.BUCKET_STATUSES["out"] == ("ready_for_delivery", "out_for_delivery")
    assert repo.BUCKET_STATUSES["completed"] == ("completed",)
    assert repo.BUCKET_STATUSES["attention"] == (
        "support_required", "cancellation_requested", "pickup_change_requested")


def test_bucket_where_in_and_out():
    sql, params = repo._bucket_where("in", 2)
    assert "o.status = any($2::text[])" in sql
    assert params == [list(repo.BUCKET_STATUSES["in"])]
    sql_out, params_out = repo._bucket_where("out", 2)
    assert params_out == [list(repo.BUCKET_STATUSES["out"])]


def test_bucket_where_attention_includes_open_issues():
    sql, _ = repo._bucket_where("attention", 2)
    assert "facility_issues" in sql
    assert "not in ('resolved','closed')" in sql


def test_bucket_where_upcoming_is_non_terminal_future():
    sql, params = repo._bucket_where("upcoming", 2)
    assert "pickup_date >=" in sql
    assert params == [list(repo._NON_TERMINAL_EXCLUDE)]
    # excludes draft + terminal statuses
    assert set(repo._NON_TERMINAL_EXCLUDE) == {"draft", "completed", "cancelled", "abandoned"}


def test_bucket_where_all_has_no_status_filter():
    sql, params = repo._bucket_where("all", 2)
    assert sql == "true"
    assert params == []


# --------------------------- PII-safe serializer (14) --------------------
def _row_with_pii():
    return {
        "id": "uuid-1",
        "order_id": "LK-2026-000004",
        "status": "in_cleaning",
        "service": "Wash & Fold",
        "service_display_name": "Wash & Fold",
        "catalogue_category_name": "Everyday",
        "line_items": [{"name": "Shirt", "quantity": 3, "line_total": 30}],
        "pickup_area": "Dubai Marina",
        "city": "Dubai",
        "pickup_emirate": "Dubai",
        "pickup_instruction_text": "Ring the bell twice",
        "turnaround_text": "48 hours",
        "estimated_delivery_text": "Wed 6pm",
        "express_eligible": True,
        "pickup_date": "2026-07-28",
        "pickup_slot": "9am-11am",
        "estimated_total": 30,
        "driver": "Ravi",
        "customer_name": "Aisha Rahman",
        # --- fields that MUST NEVER leak ---
        "customer_phone": "+971501234567",
        "pickup_address": "Villa 12, Street 4, Dubai Marina",
        "payment_method": "card",
        "payment_status": "paid",
        "notes": "internal private note",
        "conversation_id": "conv-1",
        "customer_id": "cust-1",
    }


def test_facility_serializer_excludes_pii():
    out = repo.to_facility_read(_row_with_pii())
    forbidden = {"customer_phone", "phone", "email", "pickup_address", "address",
                 "payment_method", "notes", "conversation_id", "customer_id",
                 "customer_name"}
    assert forbidden.isdisjoint(out.keys()), f"PII leaked: {forbidden & out.keys()}"
    # Customer LABEL is the first name only.
    assert out["customer_label"] == "Aisha"
    # Operational fields ARE present.
    assert out["area"] == "Dubai Marina"
    assert out["order_value"] == 30.0
    assert out["status_label"]
    assert out["is_paid"] is True  # exposed only as a boolean, never the method


def test_facility_serializer_blank_name_is_generic_label():
    row = _row_with_pii()
    row["customer_name"] = None
    assert repo.to_facility_read(row)["customer_label"] == "Customer"


# --------------------------- action allow-list (13) ----------------------
@pytest.mark.parametrize("action", ["cancel", "refund", "change_price", "complete",
                                    "mark_completed", "mark_delivered", "reassign"])
async def test_forbidden_actions_raise(action):
    with pytest.raises(svc.ForbiddenFacilityAction):
        await svc.apply_action("FAC-1", "LK-2026-000004", action, actor_label="Owner")


async def test_unknown_action_raises_invalid():
    with pytest.raises(svc.InvalidFacilityAction):
        await svc.apply_action("FAC-1", "LK-2026-000004", "teleport", actor_label="Owner")


def test_allowed_actions_shape():
    # Every allowed action moves within the facility middle-of-lifecycle only.
    assert svc.ALLOWED_ACTIONS["mark_ready"]["to"] == "ready_for_delivery"
    assert svc.ALLOWED_ACTIONS["confirm_handoff"]["to"] == "out_for_delivery"
    # accept + QC record an event but do NOT change status.
    assert svc.ALLOWED_ACTIONS["accept"]["to"] is None
    assert svc.ALLOWED_ACTIONS["move_to_qc"]["to"] is None
    # No allowed action ever completes/cancels an order.
    assert "completed" not in {a["to"] for a in svc.ALLOWED_ACTIONS.values()}
    assert "cancelled" not in {a["to"] for a in svc.ALLOWED_ACTIONS.values()}


async def test_action_rejects_illegal_transition(monkeypatch):
    # start_cleaning is only valid from picked_up; from 'completed' it must fail.
    async def fake_get_row(facility_id, order_id):
        return {"id": "u1", "status": "completed", "order_id": order_id}

    monkeypatch.setattr(repo, "get_row", fake_get_row)
    with pytest.raises(svc.InvalidFacilityAction):
        await svc.apply_action("FAC-1", "LK-1", "start_cleaning", actor_label="Owner")
