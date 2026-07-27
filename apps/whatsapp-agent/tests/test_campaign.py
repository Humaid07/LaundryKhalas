"""Campaign eligibility + last-touch attribution (pure) + the eligibility tool."""
import datetime as _dt
import json

from agents.whatsapp_agent.booking_tools import BookingContext, make_booking_executor
from services import campaign


TODAY = _dt.date(2026, 7, 25)


# --------------------------- eligibility ---------------------------------
def test_active_campaign_eligible_in_window_and_market():
    c = campaign.find_by_code("NEW25-AE")
    assert campaign.is_eligible(c, TODAY, market="AE")
    # Wrong market excluded.
    assert not campaign.is_eligible(c, TODAY, market="QA")


def test_expired_campaign_not_eligible():
    c = campaign.find_by_code("EXPIRED-TEST")
    assert not campaign.is_eligible(c, TODAY, market="AE")


def test_eligible_campaigns_excludes_expired():
    codes = {c["code"] for c in campaign.eligible_campaigns(TODAY, market="AE")}
    assert "NEW25-AE" in codes and "EXPIRED-TEST" not in codes


def test_before_valid_from_not_eligible():
    c = campaign.find_by_code("NEW25-AE")
    assert not campaign.is_eligible(c, _dt.date(2026, 6, 1), market="AE")


# --------------------------- last-touch attribution ----------------------
def test_pick_last_touch_most_recent_within_window():
    booking = _dt.datetime(2026, 7, 25, 12, 0)
    sends = [
        {"campaign_id": "A", "sent_at": _dt.datetime(2026, 7, 1, 9, 0)},
        {"campaign_id": "B", "sent_at": _dt.datetime(2026, 7, 20, 9, 0)},   # most recent in window
        {"campaign_id": "C", "sent_at": _dt.datetime(2026, 7, 26, 9, 0)},   # after booking → ignored
    ]
    best = campaign.pick_last_touch(sends, booking, window_days=30)
    assert best["campaign_id"] == "B"


def test_pick_last_touch_none_outside_window():
    booking = _dt.datetime(2026, 7, 25, 12, 0)
    sends = [{"campaign_id": "A", "sent_at": _dt.datetime(2026, 6, 1, 9, 0)}]  # 54 days before
    assert campaign.pick_last_touch(sends, booking, window_days=30) is None


# --------------------------- eligibility tool ----------------------------
class _Repo:
    conversation_id = "conv-1"
    async def get_active_draft(self, cid):
        return None


def _ctx(market="AE"):
    ctx = BookingContext(
        conversation_id="conv-1", order_uuid="o1", repo=_Repo(), today=TODAY,
        available_slots=None, customer={"id": "c", "market": market})
    return make_booking_executor(ctx)


async def test_tool_lists_active_offers():
    execute = _ctx()
    out, err = await execute("get_campaign_eligibility", {})
    data = json.loads(out)
    assert not err
    codes = {c["code"] for c in data["eligible_campaigns"]}
    assert "NEW25-AE" in codes and "EXPIRED-TEST" not in codes


async def test_tool_rejects_expired_code():
    execute = _ctx()
    out, _ = await execute("get_campaign_eligibility", {"offer_code": "EXPIRED-TEST"})
    data = json.loads(out)
    assert data["eligible"] is False and data["reason"] == "expired_or_ineligible"


async def test_tool_unknown_offer():
    execute = _ctx()
    out, _ = await execute("get_campaign_eligibility", {"offer_code": "NOPE"})
    data = json.loads(out)
    assert data["found"] is False
