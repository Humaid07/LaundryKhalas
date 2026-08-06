"""Proactive outbound facility-quote push: gate, idempotency, send."""
from db import database
from services import quote_outbound as qo


def _pending():
    return {"revision_id": "r1", "order_item_id": "li-1", "quote_version": 2,
            "final_price": 140.0, "currency": "AED", "relay_text": "The facility has checked the item. "
            "The final price is AED 140. Shall I proceed?"}


class _FakeChannel:
    sent: list = []

    @classmethod
    def from_settings(cls):
        return cls()

    async def send_text(self, *, to_phone, text):
        _FakeChannel.sent.append((to_phone, text))
        return "wamid.1"


def _wire(monkeypatch, *, pending=True, claim=True, phone="+971500000001", may_send=True):
    _FakeChannel.sent = []

    async def get_pending(order_uuid):
        return _pending() if pending else None

    async def mark_sent(rid):
        return _pending() if claim else None

    async def fetchval(sql, *a):
        return "conv-1"

    async def get_phone(cid):
        return phone

    async def create_event(**kw):
        return {}

    monkeypatch.setattr(database, "is_supabase_mode", lambda: True)
    monkeypatch.setattr(qo.facility_quote_workflow, "get_pending_quote_for_order", get_pending)
    monkeypatch.setattr(qo.facility_quote_revisions_repo, "mark_sent_to_customer", mark_sent)
    monkeypatch.setattr(database, "fetchval", fetchval)
    monkeypatch.setattr(qo.conversations_repo, "get_customer_phone", get_phone)
    monkeypatch.setattr(qo.order_events_repo, "create", create_event)
    monkeypatch.setattr(qo, "EvolutionWhatsAppChannel", _FakeChannel)
    monkeypatch.setattr(qo, "_may_send", lambda p: may_send)


async def test_push_sends_confirmed_price(monkeypatch):
    _wire(monkeypatch)
    out = await qo.send_customer_quote("o1", order_ref="LK-1")
    assert out["sent"] is True and out["final_price"] == 140.0
    assert len(_FakeChannel.sent) == 1
    to, text = _FakeChannel.sent[0]
    assert to == "+971500000001" and "final price is AED 140" in text and "Shall I proceed?" in text


async def test_push_idempotent_when_already_sent(monkeypatch):
    _wire(monkeypatch, claim=False)  # mark_sent_to_customer returns None → already sent
    out = await qo.send_customer_quote("o1")
    assert out["sent"] is False and out["reason"] == "already_sent"
    assert _FakeChannel.sent == []


async def test_push_skips_when_no_pending(monkeypatch):
    _wire(monkeypatch, pending=False)
    out = await qo.send_customer_quote("o1")
    assert out["sent"] is False and out["reason"] == "no_pending_quote"


async def test_push_respects_outbound_gate(monkeypatch):
    _wire(monkeypatch, may_send=False)   # paused / not allow-listed
    out = await qo.send_customer_quote("o1")
    assert out["sent"] is False and out["reason"] == "outbound_gated"
    assert _FakeChannel.sent == []       # nothing sent
