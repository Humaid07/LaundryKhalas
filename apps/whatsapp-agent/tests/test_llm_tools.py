"""The grounded backend tool layer (agents/whatsapp_agent/llm_tools.py).

These verify the tools stay honest: they read the deterministic engines, never
invent a price/turnaround/coverage, and reject bad/unknown input safely — the
guarantees that let Claude phrase an answer without being able to fabricate one.
"""
import json

import pytest

from agents.whatsapp_agent.llm_tools import TOOL_SCHEMAS, execute_tool
from services import catalogue


async def _call(name, **inp):
    text, is_error = await execute_tool(name, inp)
    return json.loads(text), is_error


def test_schemas_are_strict_and_named():
    for t in TOOL_SCHEMAS:
        assert t["name"] and t["description"]
        schema = t["input_schema"]
        assert schema["type"] == "object"
        # strict-friendly: closed object so tool inputs validate exactly
        assert schema.get("additionalProperties") is False


async def test_unknown_tool_is_rejected_not_raised():
    result, is_error = await _call("delete_everything", x=1)
    assert is_error is True
    assert "Unknown tool" in result["error"]


async def test_missing_required_input_is_rejected():
    data, err = await _call("lookup_item_price")  # no query
    assert err is True
    assert "required" in data["error"]
    data, err = await _call("check_service_area")  # no area
    assert err is True
    assert "required" in data["error"]


async def test_lookup_unknown_item_never_invents_a_price():
    data, err = await _call("lookup_item_price", query="a flux capacitor")
    assert err is False
    assert data["match"] == "none"
    assert "invent" in data["guidance"].lower()
    # no price fields leaked on a non-match
    assert "price_label" not in data


async def test_lookup_ambiguous_item_asks_instead_of_guessing():
    # "shirt" intentionally spans Clean & Press and Press Only in the catalogue.
    data, err = await _call("lookup_item_price", query="shirt")
    assert err is False
    assert data["match"] == "ambiguous"
    assert len(data["candidates"]) >= 2
    assert "which" in data["guidance"].lower()


async def test_lookup_measured_item_is_not_a_firm_total():
    # A per-sqm item (carpet) must never be presented as a firm quotable total.
    data, err = await _call("lookup_item_price", query="carpet")
    assert err is False
    assert data["match"] == "ok"
    assert data["is_firm_price"] is False
    assert "inspection" in data["guidance"].lower() or "measure" in data["guidance"].lower()


async def test_lookup_firm_item_is_quotable():
    firm = None
    for it in catalogue.all_items():
        if (
            it["pricing_type"] in ("FIXED_PER_ITEM", "PER_PAIR", "PER_BAG")
            and not it["is_starting_price"]
            and not it["requires_inspection"]
            and not it["requires_measurement"]
            and it["current_price"] is not None
        ):
            codes, reason = catalogue.resolve_item_alias(it["canonical_name"])
            if reason == "ok" and codes == [it["item_code"]]:
                firm = it
                break
    if firm is None:
        pytest.skip("no uniquely-resolvable firm item in the catalogue")
    data, err = await _call("lookup_item_price", query=firm["canonical_name"])
    assert err is False
    assert data["match"] == "ok"
    assert data["is_firm_price"] is True
    assert data["item_code"] == firm["item_code"]


async def test_list_categories_is_grounded():
    data, err = await _call("list_service_categories")
    assert err is False
    names = {c["name"] for c in data["categories"]}
    expected = {c["name"] for c in catalogue.categories()}
    assert names == expected


async def test_estimate_turnaround_returns_configured_sla():
    data, err = await _call("estimate_turnaround", query="carpet")
    assert err is False
    assert data["standard_turnaround"]  # never empty
    assert "matched_items" in data
    # never promises an exact hour beyond the engine text
    assert "never" in data["guidance"].lower()


async def test_estimate_turnaround_unmatched_still_safe():
    data, err = await _call("estimate_turnaround", query="qwertyuiop")
    assert err is False
    assert data["matched_items"] == 0
    assert data["standard_turnaround"]  # falls back to the safe default rule


async def test_check_service_area_recognised():
    data, err = await _call("check_service_area", area="Dubai Marina")
    assert err is False
    assert data["recognised"] is True
    assert data["area"] == "Dubai Marina"


async def test_check_service_area_unknown_defers_not_denies():
    data, err = await _call("check_service_area", area="Narnia")
    assert err is False
    assert data["recognised"] is False
    # must not claim coverage either way
    assert "confirm" in data["guidance"].lower()
