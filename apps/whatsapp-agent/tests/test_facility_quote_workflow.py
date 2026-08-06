"""Facility quote workflow: markup snapshot, ops-review gate, versioned approval."""
from db.repositories import customer_quote_repo
from services import facility_quote_workflow as wf


def _snap_row():
    return {"id": "s1", "facility_fee": 100, "markup_type": "percentage", "markup_value": 40,
            "markup_rule_id": "DEFAULT-40", "customer_subtotal": 140, "final_customer_price": 140,
            "currency": "AED", "order_id": "o1", "order_item_id": "li-1"}


# ---------------------------- fee privacy --------------------------------
def test_snapshot_customer_safe_strips_fee():
    out = customer_quote_repo.snapshot_to_read(_snap_row(), include_fee=False)
    assert "facility_fee" not in out and "markup_value" not in out
    assert out["final_customer_price"] == 140


def test_snapshot_internal_includes_fee():
    out = customer_quote_repo.snapshot_to_read(_snap_row(), include_fee=True)
    assert out["facility_fee"] == 100


# ---------------------------- price + review -----------------------------
async def test_price_facility_quote_high_value_needs_review(monkeypatch):
    async def margin(*, bespoke=False, service_code=None):
        return {"id": "DEFAULT-40", "margin_type": "percentage", "margin_value": 40}

    async def create_snapshot(**kw):
        return {**kw["snapshot"], "id": "snap1"}

    monkeypatch.setattr(wf.facility_pricing_repo, "get_margin_rule", margin)
    monkeypatch.setattr(wf.customer_quote_repo, "create_snapshot", create_snapshot)
    out = await wf.price_facility_quote(revision_id="r1", order_id="o1", order_item_id="li-1",
                                        quote_version=1, facility_fee=300)  # 300*1.4=420 ≥ 300
    assert out["ok"] is True
    assert out["final_customer_price"] == 420.0
    assert out["requires_operations_review"] is True
    assert "ABOVE_AMOUNT_THRESHOLD" in out["review_reasons"]


async def test_price_facility_quote_normal_no_review(monkeypatch):
    async def margin(*, bespoke=False, service_code=None):
        return {"margin_type": "percentage", "margin_value": 40}

    async def create_snapshot(**kw):
        return {**kw["snapshot"], "id": "snap1"}

    monkeypatch.setattr(wf.facility_pricing_repo, "get_margin_rule", margin)
    monkeypatch.setattr(wf.customer_quote_repo, "create_snapshot", create_snapshot)
    out = await wf.price_facility_quote(revision_id="r1", order_id="o1", order_item_id="li-1",
                                        quote_version=1, facility_fee=80)  # 112, under 300, 28% margin
    assert out["requires_operations_review"] is False


async def test_invalid_fee_rejected(monkeypatch):
    out = await wf.price_facility_quote(revision_id="r1", order_id="o1", order_item_id="li-1",
                                        quote_version=1, facility_fee=0)
    assert out["ok"] is False and out["reason"] == "invalid_fee"


# --------------------------- versioned approval --------------------------
async def test_record_decision_idempotent_per_version(monkeypatch):
    seen = {"count": 0}

    async def record_approval(**kw):
        seen["count"] += 1
        return None if seen["count"] > 1 else {"id": "a1", **kw}

    monkeypatch.setattr(wf.customer_quote_repo, "record_approval", record_approval)
    first = await wf.record_customer_decision(order_id="o1", order_item_id="li-1", revision_id="r1",
                                              quote_version=1, decision="APPROVED", final_price=140)
    dup = await wf.record_customer_decision(order_id="o1", order_item_id="li-1", revision_id="r1",
                                            quote_version=1, decision="APPROVED", final_price=140)
    assert first is not None and dup is None  # idempotent: no second approval row
