"""Phase 3: silent CUSTOMER_CONVERSION_REVIEW pending task (spec §9/§18)."""
import pytest

from services import negotiation_review as nr
from services import pending_tasks


def test_task_type_registered():
    assert pending_tasks.is_valid_type("CUSTOMER_CONVERSION_REVIEW")
    sla = pending_tasks.get_sla("CUSTOMER_CONVERSION_REVIEW")
    assert sla["escalation_team"]


def test_build_review_notes_carries_internal_context():
    notes = nr.build_review_notes(
        "DISCOUNT_LIMIT_REACHED",
        {"service": "Dry Clean", "current_price": "AED 120", "existing_discount": "25%",
         "max_discount": "25%", "facility_cost": "AED 60", "recent_messages": ["too expensive"],
         "hesitation": "PRICE_OBJECTION", "state": "waiting_for_confirmation"},
    )
    assert "DISCOUNT_LIMIT_REACHED" in notes
    for needle in ("Dry Clean", "AED 120", "25%", "AED 60", "too expensive", "PRICE_OBJECTION"):
        assert needle in notes


class _FakeRepo:
    def __init__(self, open_exists=False):
        self.open_exists = open_exists
        self.created = []

    async def has_open(self, conversation_id, task_type):
        return self.open_exists

    async def create(self, task_type, **kw):
        self.created.append((task_type, kw))
        return {"id": "task-1", "task_type": task_type, **kw}


@pytest.mark.asyncio
async def test_flag_creates_when_none_open():
    repo = _FakeRepo(open_exists=False)
    created = await nr.flag_conversion_review(
        repo=repo, conversation_id="c1", customer_id="cust1", order_id="o1",
        reason="DISCOUNT_LIMIT_REACHED", context={"service": "Dry Clean"})
    assert created is True
    assert repo.created and repo.created[0][0] == "CUSTOMER_CONVERSION_REVIEW"
    assert "DISCOUNT_LIMIT_REACHED" in repo.created[0][1]["notes"]


@pytest.mark.asyncio
async def test_flag_deduped_when_open_exists():
    repo = _FakeRepo(open_exists=True)
    created = await nr.flag_conversion_review(
        repo=repo, conversation_id="c1", reason="DISCOUNT_LIMIT_REACHED", context={})
    assert created is False
    assert repo.created == []
