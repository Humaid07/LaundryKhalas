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
    ("I run an Airbnb and need the linen turned around", "airbnb"),
    ("just some shirts please", "other"),
])
def test_classify_business_type(text, expected):
    assert b2b.classify_business_type(text) == expected


def test_airbnb_may_use_consumer_pricing_others_do_not():
    assert b2b.may_use_consumer_pricing("airbnb") is True
    for bt in ("hotel", "restaurant", "uniform", "commercial_laundry",
               "bulk_outsourcing", "facility_partnership", "other"):
        assert b2b.may_use_consumer_pricing(bt) is False


def test_qualifying_fields_cover_spec_18():
    for field in ("business name", "email", "estimated weekly volume", "frequency",
                  "location", "preferred contact method"):
        assert field in b2b.QUALIFYING_FIELDS


def test_trial_note_never_promises_free_large_trial():
    note = b2b.trial_note().lower()
    assert "small trial" in note and "no charge" in note   # small trial may be free
    assert "larger trial may be chargeable" in note        # large trial is NOT free
    assert "aed" not in note and "%" not in note


def test_acknowledgement_asks_for_email_and_airbnb_note():
    assert "email" in b2b.acknowledgement("hotel")
    assert "small Airbnb" in b2b.acknowledgement("airbnb")


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
