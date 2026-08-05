"""Alteration price matrix (services/alterations, spec §18)."""
import pytest

from services import alterations as alt


@pytest.fixture(autouse=True)
def _fresh():
    alt.reload_config()
    yield
    alt.reload_config()


def _q(text, **kw):
    return alt.resolve_alteration(text, **kw)


# --- trouser shortening: base / pushback / quantity (>5) ---------------------
def test_trouser_shortening_base_pushback_quantity():
    assert _q("shorten my trousers").unit_price == 40
    assert _q("shorten my trousers", pushback=True).unit_price == 35
    q = _q("shorten trousers", quantity=6)
    assert q.unit_price == 30 and q.total == 180        # 6 x 30
    # 5 items is NOT the quantity tier (spec: more than five)
    assert _q("shorten trousers", quantity=5).unit_price == 40


def test_dress_shortening_tiers():
    assert _q("shorten dress").unit_price == 45
    assert _q("shorten dress", pushback=True).unit_price == 40
    assert _q("shorten dress", quantity=2).unit_price == 35


def test_sleeve_shortening_shirt_vs_jacket():
    assert _q("shorten shirt sleeves").unit_price == 35
    assert _q("jacket sleeve shortening").unit_price == 65


def test_waist_reduction_and_expansion():
    assert _q("waist reduction").unit_price == 40
    assert _q("waist reduction", pushback=True).unit_price == 35
    assert _q("waist reduction", quantity=2).unit_price == 30
    assert _q("waist expansion").unit_price == 45
    assert _q("waist expansion", pushback=True).unit_price == 40
    assert _q("waist expansion", quantity=2).unit_price == 35


def test_loosening_flat_35():
    assert _q("loosen trousers").unit_price == 35
    assert _q("loosen shirts").unit_price == 35


def test_zip_replacement_supplier_and_length():
    assert _q("replace small zip").unit_price == 40             # our zip
    assert _q("small zip my own").unit_price == 30             # customer zip
    assert _q("replace long zip").unit_price == 60             # our zip
    assert _q("long zip my own").unit_price == 50              # customer zip


def test_button_replacement_per_button():
    q = _q("replace buttons", quantity=3)
    assert q.unit_price == 10 and q.total == 30


# --- facility quotation for unlisted alterations (no invented price) ---------
@pytest.mark.parametrize("text", ["basic hemming", "minor tear", "lining repair", "generic tightening"])
def test_unlisted_alterations_route_to_facility_quote(text):
    q = _q(text)
    assert q.matched is True and q.facility_quote is True
    assert q.unit_price is None and q.total is None
    assert alt.FACILITY_QUOTE_REPLY == "Let me confirm the price for that and get back to you."


def test_non_alteration_text_is_unmatched():
    q = _q("do you clean carpets")
    assert q.matched is False and q.facility_quote is False


def test_rule_version_stamped():
    assert _q("shorten trousers").rule_version == "2026_08_05"


# --- grounding tool wiring (lookup_alteration_price) -------------------------
async def test_tool_returns_exact_price():
    import json

    from agents.whatsapp_agent import llm_tools
    text, err = await llm_tools.execute_tool(
        "lookup_alteration_price", {"description": "shorten my trousers", "quantity": 6})
    assert err is False
    data = json.loads(text)
    assert data["match"] == "ok" and data["type"] == "TROUSER_SHORTEN"
    assert data["unit_price"] == 30 and data["total"] == 180   # 6+ tier


async def test_tool_routes_unlisted_to_facility_quote():
    import json

    from agents.whatsapp_agent import llm_tools
    text, err = await llm_tools.execute_tool(
        "lookup_alteration_price", {"description": "repair the lining"})
    data = json.loads(text)
    assert data["match"] == "facility_quote"
    assert data["reply"] == alt.FACILITY_QUOTE_REPLY


async def test_tool_requires_description():
    from agents.whatsapp_agent import llm_tools
    _, err = await llm_tools.execute_tool("lookup_alteration_price", {"description": ""})
    assert err is True
