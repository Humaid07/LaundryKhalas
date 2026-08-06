"""Live facility-quote relay: present pending price + record customer decision."""
from services import facility_quote_workflow as wf


def _rev(**over):
    base = {"id": "r1", "order_id": "o1", "order_item_id": "li-1", "quote_version": 2,
            "customer_price": 140.0, "currency": "AED", "facility_issue_id": "iss1",
            "reason": "extra restoration"}
    base.update(over)
    return base


async def test_get_pending_quote_presents_final_price(monkeypatch):
    async def latest(order_uuid):
        return _rev()
    monkeypatch.setattr(wf.facility_quote_revisions_repo, "latest_pending_for_order", latest)
    out = await wf.get_pending_quote_for_order("o1")
    assert out["final_price"] == 140.0 and out["quote_version"] == 2
    assert "final price is AED 140" in out["relay_text"] and "Shall I proceed?" in out["relay_text"]
    assert "facility_fee" not in out  # customer-safe


async def test_get_pending_quote_none_when_nothing_pending(monkeypatch):
    async def latest(order_uuid):
        return None
    monkeypatch.setattr(wf.facility_quote_revisions_repo, "latest_pending_for_order", latest)
    assert await wf.get_pending_quote_for_order("o1") is None


async def test_apply_decision_approved_unblocks(monkeypatch):
    calls = {"approval": None, "decision": None, "issue": None, "event": None}

    async def latest(order_uuid):
        return _rev()

    async def record_approval(**kw):
        calls["approval"] = kw
        return {"id": "a1", **kw}

    async def set_decision(rid, *, status):
        calls["decision"] = (rid, status)
        return {}

    async def set_issue_status(iid, status):
        calls["issue"] = (iid, status)
        return {}

    async def create_event(**kw):
        calls["event"] = kw
        return {}

    monkeypatch.setattr(wf.facility_quote_revisions_repo, "latest_pending_for_order", latest)
    monkeypatch.setattr(wf.customer_quote_repo, "record_approval", record_approval)
    monkeypatch.setattr(wf.facility_quote_revisions_repo, "set_customer_decision", set_decision)
    monkeypatch.setattr(wf.facility_issues_repo, "set_status", set_issue_status)
    monkeypatch.setattr(wf.order_events_repo, "create", create_event)

    out = await wf.apply_customer_decision("o1", "LK-1", decision="approved")
    assert out["ok"] and out["decision"] == "APPROVED" and out["unblocked"] is True
    assert calls["approval"]["quote_version"] == 2 and calls["approval"]["decision"] == "APPROVED"
    assert calls["decision"] == ("r1", "customer_approved")
    assert calls["issue"] == ("iss1", "resolved")          # facility unblocked
    assert calls["event"]["event_type"] == "facility_processing_authorized"


async def test_apply_decision_declined_does_not_unblock(monkeypatch):
    async def latest(order_uuid):
        return _rev()

    async def noop(*a, **k):
        return {}

    monkeypatch.setattr(wf.facility_quote_revisions_repo, "latest_pending_for_order", latest)
    monkeypatch.setattr(wf.customer_quote_repo, "record_approval", noop)
    monkeypatch.setattr(wf.facility_quote_revisions_repo, "set_customer_decision", noop)
    monkeypatch.setattr(wf.facility_issues_repo, "set_status", noop)
    monkeypatch.setattr(wf.order_events_repo, "create", noop)
    out = await wf.apply_customer_decision("o1", "LK-1", decision="declined")
    assert out["ok"] and out["decision"] == "DECLINED" and out["unblocked"] is False


async def test_apply_decision_no_pending_quote(monkeypatch):
    async def latest(order_uuid):
        return None
    monkeypatch.setattr(wf.facility_quote_revisions_repo, "latest_pending_for_order", latest)
    out = await wf.apply_customer_decision("o1", "LK-1", decision="approved")
    assert out["ok"] is False and out["reason"] == "no_pending_quote"
