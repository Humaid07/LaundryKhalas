"""Complaint classification + empathetic-ack tests (pure) + repo guards."""
import pytest

from db import database
from db.repositories import complaints_repo
from services import complaints


# --------------------------- classification ------------------------------
@pytest.mark.parametrize("text,expected", [
    ("my shirt was damaged and torn", "damage"),
    ("the sweater shrunk after cleaning", "shrinking"),
    ("clothes came back still wet and damp", "damp"),
    ("one shirt is missing from my order", "missing_items"),
    ("it's still dirty, there's a stain", "poor_cleaning"),
    ("the trousers are not pressed, all wrinkled", "poor_pressing"),
    ("the hem is too short now, wrong size", "incorrect_alteration"),
    ("please clean it again, redo it", "reprocessing"),
    ("you never collected my laundry, late pickup", "delay_collection"),
    ("my order was not delivered, late delivery", "delay_delivery"),
    ("I want a refund", "refund_request"),
])
def test_classify_category_keywords(text, expected):
    assert complaints.classify_category(text) == expected


def test_classify_falls_back_to_escalation_category():
    assert complaints.classify_category("I'm unhappy", "late_delivery") == "delay_delivery"
    assert complaints.classify_category("bad service", "complaint") == "other"


def test_classify_unknown_is_other():
    assert complaints.classify_category("hello there") == "other"


def test_detect_requested_resolution():
    assert complaints.detect_requested_resolution("I want my money back") == "refund"
    assert complaints.detect_requested_resolution("please replace it") == "replacement"
    assert complaints.detect_requested_resolution("just clean it again") == "reclean"
    assert complaints.detect_requested_resolution("this is bad") == "unknown"


def test_urgency_from_priority():
    assert complaints.urgency_from_priority("urgent") == "urgent"
    assert complaints.urgency_from_priority(None) == "medium"


# --------------------------- empathetic ack ------------------------------
_FORBIDDEN = ("refund", "compensat", "replace", "guarantee", "reimburse")


def test_ack_never_promises_compensation():
    for cat in complaints.CATEGORIES:
        for has_ref in (True, False):
            for has_photo in (True, False):
                msg = complaints.empathetic_ack(cat, has_order_ref=has_ref, has_photo=has_photo).lower()
                assert not any(w in msg for w in _FORBIDDEN), f"{cat}: {msg}"


def test_ack_asks_for_both_when_missing():
    msg = complaints.empathetic_ack("damage", has_order_ref=False, has_photo=False)
    assert "order reference" in msg and "photo" in msg


def test_ack_asks_only_order_ref_when_photo_present():
    msg = complaints.empathetic_ack("damage", has_order_ref=False, has_photo=True)
    assert "order reference" in msg and "photo" not in msg


def test_ack_no_photo_request_for_non_visual_category():
    # A delay complaint doesn't need a photo.
    msg = complaints.empathetic_ack("delay_delivery", has_order_ref=True, has_photo=False)
    assert "photo" not in msg
    assert "sorry" in msg.lower()


# --------------------------- repo guard ----------------------------------
async def test_create_coerces_unknown_category(monkeypatch):
    captured = {}

    async def fake_fetchrow(sql, *args):
        captured["args"] = args
        return None

    monkeypatch.setattr(database, "fetchrow", fake_fetchrow)
    await complaints_repo.create(customer_id="c1", conversation_id="cv1",
                                 category="totally_made_up")
    # category is arg index 5 (1-based $6): customer, convo, order_id, order_ref, category...
    assert captured["args"][4] == "other"
