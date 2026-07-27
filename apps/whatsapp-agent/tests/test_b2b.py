"""B2B classification + acknowledgement (pure) + lead-repo guards."""
import pytest

from db import database
from db.repositories import b2b_leads_repo
from services import b2b


@pytest.mark.parametrize("text,expected", [
    ("We run a hotel and need guest laundry", "hotel"),
    ("Restaurant linen and napkins weekly", "restaurant"),
    ("We need staff uniform cleaning", "uniform"),
    ("Interested in a facility partnership to supply you", "facility_partnership"),
    ("We want to outsource bulk laundry, large volume", "bulk_outsourcing"),
    ("Looking for commercial laundry for our company", "commercial_laundry"),
    ("just some shirts please", "other"),
])
def test_classify_business_type(text, expected):
    assert b2b.classify_business_type(text) == expected


def test_acknowledgement_routes_and_never_quotes_price():
    for bt in b2b.BUSINESS_TYPES:
        msg = b2b.acknowledgement(bt).lower()
        assert "team" in msg  # routed to the commercial team
        # Never quotes a price or currency in a B2B auto-ack.
        assert "aed" not in msg and "price" not in msg and "%" not in msg


def test_acknowledgement_asks_for_qualifiers():
    msg = b2b.acknowledgement("hotel")
    assert "company name" in msg and "volume" in msg


async def test_create_coerces_unknown_business_type(monkeypatch):
    captured = {}

    async def fake_fetchrow(sql, *args):
        captured["args"] = args
        return None

    monkeypatch.setattr(database, "fetchrow", fake_fetchrow)
    await b2b_leads_repo.create(customer_id="c1", conversation_id="cv1",
                                business_type="totally_made_up")
    # business_type is arg index 2 ($3).
    assert captured["args"][2] == "other"


async def test_update_details_whitelists_columns(monkeypatch):
    captured = {}

    async def fake_fetchrow(sql, *args):
        captured["sql"] = sql
        captured["args"] = args
        return None

    monkeypatch.setattr(database, "fetchrow", fake_fetchrow)
    await b2b_leads_repo.update_details("lead-1", company_name="Acme Hotels",
                                        estimated_volume="500kg/wk",
                                        evil_column="DROP TABLE")
    # Only whitelisted columns appear; the injected column is ignored.
    assert "company_name" in captured["sql"] and "estimated_volume" in captured["sql"]
    assert "evil_column" not in captured["sql"]
