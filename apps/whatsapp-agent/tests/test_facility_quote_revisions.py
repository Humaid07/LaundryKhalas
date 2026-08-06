"""Quote-revision repo: fee privacy, status mapping, scoped SQL (Area 6)."""
from db import database
from db.repositories import facility_quote_revisions_repo as repo


def _row():
    return {
        "id": "r1", "order_id": "o1", "order_item_id": "li-1", "facility_id": "F1",
        "facility_issue_id": "i1", "facility_fee": 40, "currency": "AED", "reason": "extra",
        "customer_price": 52, "status": "customer_pending", "created_by_label": "Jane",
        "reviewed_by": None, "reviewed_at": None, "customer_decided_at": None,
        "created_at": "t", "updated_at": "t",
    }


def test_to_read_includes_fee_for_facility():
    out = repo.to_read(_row(), include_fee=True)
    assert out["facility_fee"] == 40.0
    assert out["customer_price"] == 52.0


def test_to_read_strips_fee_for_customer_paths():
    out = repo.to_read(_row(), include_fee=False)
    assert "facility_fee" not in out          # facility fee never on a customer path
    assert out["customer_price"] == 52.0      # only the customer price remains


async def test_create_is_scoped_and_returns_read(monkeypatch):
    captured = {}

    async def fake_fetchrow(sql, *args):
        captured["sql"] = sql
        captured["args"] = args
        return _row()

    monkeypatch.setattr(database, "fetchrow", fake_fetchrow)
    out = await repo.create(order_uuid="o1", facility_id="F1", facility_fee=40, order_item_id="li-1")
    assert "insert into facility_quote_revisions" in captured["sql"]
    assert "pending_ops_review" in captured["sql"]
    assert out["id"] == "r1"


async def test_status_for_order_maps_latest(monkeypatch):
    async def fetch_pending(sql, *a):
        return [{"status": "customer_pending"}, {"status": "pending_ops_review"}]

    monkeypatch.setattr(database, "fetch", fetch_pending)
    assert await repo.status_for_order("o1") == "customer_pending"

    async def fetch_approved(sql, *a):
        return [{"status": "customer_approved"}]

    monkeypatch.setattr(database, "fetch", fetch_approved)
    assert await repo.status_for_order("o1") == "approved"

    async def fetch_none(sql, *a):
        return []

    monkeypatch.setattr(database, "fetch", fetch_none)
    assert await repo.status_for_order("o1") == "none"
