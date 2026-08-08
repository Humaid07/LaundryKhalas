"""Deterministic catalogue + pricing tests.

These assert the imported catalogue matches the approved Laundry Khalas
price-list image and that the VAT-aware quote engine never turns a starting/
inspection price into a guaranteed total. No DB, no network, no image reading —
pure functions over ``config/laundry_catalogue.json`` (task spec §§13/14/15).
"""
from __future__ import annotations

from services import catalogue, pricing

# Fixture metadata (task spec §13) — the approved catalogue these tests pin to.
CATALOGUE_FIXTURE = {
    "catalogue": "Laundry Khalas UAE",
    "currency": "AED",
    "vat_rate": 0.05,
    "prices_include_vat": True,
    "source": "Approved Laundry Khalas price-list image",
    "verified_at": "2026-07-23",
}


def _price(code: str):
    item = catalogue.item_by_code(code)
    assert item is not None, f"missing catalogue item {code}"
    return item


# --- Catalogue metadata ------------------------------------------------------
def test_catalogue_metadata_matches_fixture():
    m = catalogue.meta()
    assert m["currency"] == CATALOGUE_FIXTURE["currency"]
    assert m["vat_rate"] == CATALOGUE_FIXTURE["vat_rate"]
    assert m["prices_include_vat"] is True
    assert m["verified_at"] == CATALOGUE_FIXTURE["verified_at"]


def test_categories_imported():
    # Carpet Cleaning + Curtain Cleaning were promoted out of HOME_CARE into their
    # own top-level categories so facilities can accept them individually (spec §3).
    # LEATHER_CARE added 2026-08 (founder rules doc: leather garments get a
    # From-price + inspection/photo instead of no quote at all).
    codes = [c["code"] for c in catalogue.categories()]
    assert codes == [
        "CLEAN_PRESS", "PRESS_ONLY", "HOME_CARE", "WASH_FOLD", "SHOE_CARE",
        "BAG_CARE", "SOFT_TOY", "RESTORATION", "ALTERATIONS",
        "CARPET_CLEANING", "CURTAIN_CLEANING", "LEATHER_CARE",
    ]


def test_carpet_and_curtain_are_selectable_top_level_categories():
    """Carpet/Curtain must be top-level categories (the granularity facilities
    select accepted services at) — not buried inside HOME_CARE."""
    by_code = {c["code"]: c for c in catalogue.categories()}
    assert by_code["CARPET_CLEANING"]["name"] == "Carpet Cleaning"
    assert by_code["CURTAIN_CLEANING"]["name"] == "Curtain Cleaning"
    # Item codes are preserved (order/pricing history stays intact); only their
    # parent category moved, so the same priced items now resolve under the new
    # categories and no longer appear under HOME_CARE.
    carpet = catalogue.item_by_code("HOME_CARE_CARPET_REGULAR_SQM")
    curtain = catalogue.item_by_code("HOME_CARE_CURTAIN_SQM")
    assert carpet["category_code"] == "CARPET_CLEANING"
    assert curtain["category_code"] == "CURTAIN_CLEANING"
    home_care_items = {
        it["item_code"]
        for s in catalogue.services_for_category("HOME_CARE")
        for it in catalogue.items_for_service(s["code"])
    }
    assert not any("CARPET" in c or "CURTAIN" in c for c in home_care_items)


# --- Required tests 1-13: item prices resolve to the image values ------------
def test_1_clean_press_shirt_is_9():
    item = _price("CLEAN_PRESS_SHIRT")
    assert item["current_price"] == 9
    assert item["regular_price"] == 12          # crossed-out, not the selling price
    assert item["pricing_type"] == "FIXED_PER_ITEM"
    assert item["is_starting_price"] is False


def test_2_clean_press_trousers_is_11():
    item = _price("CLEAN_PRESS_TROUSERS")
    assert item["current_price"] == 11
    assert item["regular_price"] == 14


def test_3_press_only_shirt_is_9():
    item = _price("PRESS_ONLY_SHIRT_HANGER")
    assert item["current_price"] == 9
    assert item["category_code"] == "PRESS_ONLY"


def test_4_curtain_is_20_per_sqm():
    item = _price("HOME_CARE_CURTAIN_SQM")
    assert item["current_price"] == 20
    assert item["pricing_unit"] == "SQM"
    assert item["pricing_type"] == "PER_SQM"
    assert item["requires_measurement"] is True
    assert item["regular_price"] == 25


def test_5_regular_carpet_is_20_per_sqm():
    item = _price("HOME_CARE_CARPET_REGULAR_SQM")
    assert item["current_price"] == 20
    assert item["pricing_unit"] == "SQM"
    assert item["regular_price"] == 36          # crossed-out earlier value, NOT active


def test_6_sports_sneakers_from_50_per_pair():
    item = _price("SHOE_CARE_SPORTS_SNEAKERS")
    assert item["current_price"] == 50
    assert item["is_starting_price"] is True
    assert item["pricing_unit"] == "PAIR"
    assert item["regular_price"] == 95


def test_7_formal_shoes_from_55_per_pair():
    item = _price("SHOE_CARE_FORMAL_SHOES")
    assert item["current_price"] == 55
    assert item["is_starting_price"] is True
    assert item["pricing_unit"] == "PAIR"


def test_8_wash_fold_6kg_is_60():
    item = _price("WASH_FOLD_6KG")
    assert item["current_price"] == 60
    assert item["pricing_type"] == "PER_BAG"
    assert item["bag_limit_kg"] == 6


def test_9_wash_fold_12kg_is_90():
    item = _price("WASH_FOLD_12KG")
    assert item["current_price"] == 90   # ruleset 2026_08_05 (was 80)
    assert item["bag_limit_kg"] == 12


def test_10_additional_weight_is_12_per_kg():
    item = _price("WASH_FOLD_ADDITIONAL_KG")
    assert item["current_price"] == 12   # ruleset 2026_08_05 (old AED 7 rule removed)
    assert item["pricing_type"] == "PER_KG"
    assert item["pricing_unit"] == "KG"


# --- Section 18 catalogue corrections (ruleset 2026_08_05) --------------------
def test_sole_replacement_is_facility_quote_not_550():
    item = _price("RESTORATION_SOLE_REPLACEMENT")
    assert item["current_price"] is None            # the AED 550 fixed price is gone
    assert item["pricing_type"] == "INSPECTION_REQUIRED"
    assert item["requires_inspection"] is True
    from services import catalogue as _cat
    assert _cat.item_price_label(item) == "Priced after inspection"


def test_cushion_cover_large_is_20():
    item = _price("HOME_CARE_CUSHION_COVER_LARGE")
    assert item["current_price"] == 20


def test_curtain_has_50_minimum_charge():
    item = _price("HOME_CARE_CURTAIN_SQM")
    assert item["current_price"] == 20
    assert item["minimum_charge"] == 50


def test_small_curtain_billed_at_minimum_50():
    # 2 sqm x AED 20 = 40 → floored to the AED 50 minimum.
    small = pricing.calculate_estimate(
        [{"item_code": "HOME_CARE_CURTAIN_SQM", "quantity": 1, "measure": 2}])
    assert small.customer_total == 50.0
    # 4 sqm x AED 20 = 80 → above the minimum, unchanged.
    big = pricing.calculate_estimate(
        [{"item_code": "HOME_CARE_CURTAIN_SQM", "quantity": 1, "measure": 4}])
    assert big.customer_total == 80.0


def test_11_soft_toy_small_is_49():
    item = _price("SOFT_TOY_SMALL")
    assert item["current_price"] == 49
    assert item["is_starting_price"] is False   # specialty but an exact price


def test_12_mascot_cleaning_is_161():
    item = _price("SOFT_TOY_MASCOT")
    assert item["current_price"] == 161


def test_13_alterations_from_30():
    item = _price("ALTERATIONS_GENERAL")
    assert item["current_price"] == 30
    assert item["is_starting_price"] is True
    # Standard alterations are a routine "starts from" price — no photo/inspection
    # gate (spec 2026-08-01 §5). is_starting_price still keeps it a non-firm total.
    assert item["requires_inspection"] is False


# --- Required test 14: starting prices never become guaranteed totals --------
def test_14_starting_price_is_never_a_guaranteed_total():
    q = pricing.calculate_estimate([{"item_code": "SHOE_CARE_SPORTS_SNEAKERS", "quantity": 2}])
    line = q.lines[0]
    assert line.line_kind == "pending"
    assert line.line_total is None              # 2 × 50 is NOT asserted as 100
    assert q.subtotal_excluding_vat == 0.0
    assert q.is_final is False
    text = pricing.format_quote_summary(q)
    # Starting price shown as the FINAL customer price (already inclusive: 50).
    assert "from aed 50" in text.lower()
    assert "52.50" not in text
    assert "inspection" in text.lower()


# --- Standard alterations: "starts from" price, no inspection wording (§5) ----
def test_standard_alteration_quote_reads_from_price_without_inspection():
    q = pricing.calculate_estimate([{"item_code": "ALTERATIONS_GENERAL", "quantity": 1}])
    line = q.lines[0]
    # Still a non-firm starting price (never a guaranteed total)...
    assert line.line_kind == "pending" and line.line_total is None
    assert line.requires_inspection is False
    # ...but the customer LINE wording is a clean "from AED 30 per item" with NO
    # "after inspection" tail (that tail is reserved for genuine inspection lines).
    text = " ".join(pricing.format_quote_lines(q))
    assert "from AED 30" in text
    assert "after inspection" not in text


# --- Required tests 15-18: VAT + quantity + multi-line math -------------------
def test_15_and_17_vat_and_quantity_for_exact_order():
    # 3 shirts @ 9 = 27 final (prices already inclusive; no 5% added). The
    # internal net split (27 / 1.05 = 25.71) never changes the customer total.
    q = pricing.calculate_estimate([{"item_code": "CLEAN_PRESS_SHIRT", "quantity": 3}])
    assert q.estimated_total_including_vat == 27.0        # customer pays 27
    assert q.subtotal_excluding_vat == 25.71              # internal net only
    assert q.vat_amount == 1.29
    assert q.is_final is True


def test_18_multiple_lines_sum_correctly():
    # 3 × Shirt (9) + 2 × Trousers (11) = 27 + 22 = 49 final (no 5% added).
    q = pricing.calculate_estimate([
        {"item_code": "CLEAN_PRESS_SHIRT", "quantity": 3},
        {"item_code": "CLEAN_PRESS_TROUSERS", "quantity": 2},
    ])
    assert q.estimated_total_including_vat == 49.0        # customer pays 49
    assert q.subtotal_excluding_vat == 46.67              # internal net only
    assert q.vat_amount == 2.33
    assert len(q.lines) == 2
    assert all(ln.line_kind == "exact" for ln in q.lines)


def test_16_customer_summary_shows_final_price_and_no_vat_wording():
    q = pricing.calculate_estimate([{"item_code": "CLEAN_PRESS_SHIRT", "quantity": 1}])
    d = q.to_dict()
    # Customer pays the published price unchanged (9). Internal accounting still
    # splits the tax OUT of the inclusive total (net + tax == 9), never adding.
    assert d["estimated_total_including_vat"] == 9.0
    assert d["customer_total"] == 9.0
    assert d["subtotal_excluding_vat"] == 8.57
    assert d["vat_amount"] == 0.43
    # … and the CUSTOMER-FACING summary shows only the final price, never VAT/tax.
    summary = pricing.format_quote_summary(q)
    assert "AED 9" in summary
    for banned in ("VAT", "vat", "tax", "excl", "incl", "Subtotal"):
        assert banned not in summary


def test_measured_line_is_estimate_not_final():
    # Curtain 4 sqm × 20 = 80 estimate, flagged not-final (confirmed at pickup)
    q = pricing.calculate_estimate([{"item_code": "HOME_CARE_CURTAIN_SQM", "quantity": 1, "measure": 4}])
    line = q.lines[0]
    assert line.line_kind == "estimate"
    # FINAL customer line total: 4 sqm × 20 (already inclusive) = 80.00
    assert line.line_total == 80.0
    assert line.base_line_total == 80.0
    assert q.is_final is False


# --- Required test 19: natural aliases resolve to canonical items -------------
def test_19_natural_aliases_resolve():
    # category-level
    assert catalogue.resolve_category_alias("i need my blazer dry-cleaned") == "CLEAN_PRESS"
    assert catalogue.resolve_category_alias("soft toy cleaning") == "SOFT_TOY"
    # item-level
    codes, reason = catalogue.resolve_item_alias("sneaker cleaning")
    assert reason == "ok" and codes == ["SHOE_CARE_SPORTS_SNEAKERS"]


def test_19_alter_my_trousers_maps_to_alterations():
    assert catalogue.resolve_category_alias("can you alter my trousers") == "ALTERATIONS"


# --- Required test 20: ambiguous "ironing" asks Clean & Press vs Press Only ---
def test_20_bare_ironing_is_ambiguous():
    assert catalogue.is_ambiguous_iron("can you do ironing?") is True
    assert catalogue.is_ambiguous_iron("i need pressing") is True
    # qualifiers resolve the ambiguity
    assert catalogue.is_ambiguous_iron("ironing only, already washed") is False
    assert catalogue.is_ambiguous_iron("wash and iron my shirts") is False


def test_20_ironing_only_resolves_press_only():
    assert catalogue.resolve_category_alias("ironing only please") == "PRESS_ONLY"


# --- Required test 21: interactive category + item IDs resolve ---------------
def test_21_category_option_ids_resolve():
    opts = catalogue.category_options()
    assert opts[0]["id"] == "cat:CLEAN_PRESS"
    # a rowId round-trips back to a real category
    code = opts[0]["id"].split(":", 1)[1]
    assert catalogue.category_by_code(code)["name"] == "Clean & Press"


def test_21_item_code_is_the_identifier_not_the_label():
    item = _price("CLEAN_PRESS_SHIRT")
    # identity is the stable code; the label "Shirt" is not unique across the
    # catalogue (Press Only also has a shirt) so it must never be the id
    assert item["item_code"] == "CLEAN_PRESS_SHIRT"
    press = _price("PRESS_ONLY_SHIRT_HANGER")
    assert item["item_code"] != press["item_code"]
    assert item["canonical_name"] == "Shirt"


# --- Required test 22: disabled items cannot be selected ---------------------
def test_22_disabled_item_cannot_be_selected(monkeypatch):
    catalogue.reload_catalogue()
    original = catalogue._raw()
    import copy
    patched = copy.deepcopy(original)
    # deactivate the shirt
    for cat in patched["categories"]:
        for svc in cat["services"]:
            for it in svc["items"]:
                if it["code"] == "CLEAN_PRESS_SHIRT":
                    it["active"] = False
    monkeypatch.setattr(catalogue, "_raw", lambda: patched)
    catalogue._index.cache_clear()
    try:
        assert catalogue.item_by_code("CLEAN_PRESS_SHIRT") is None
        q = pricing.calculate_estimate([{"item_code": "CLEAN_PRESS_SHIRT", "quantity": 3}])
        assert q.lines == []                    # inactive code is skipped, not priced
    finally:
        catalogue._index.cache_clear()
        catalogue.reload_catalogue()


# --- Item-code scoping (Press Only vs Clean & Press "shirt") ------------------
def test_item_alias_scoped_to_category():
    codes, reason = catalogue.resolve_item_alias("shirt", category_code="PRESS_ONLY")
    assert reason == "ok"
    assert codes == ["PRESS_ONLY_SHIRT_HANGER"]


def test_no_price_invented_for_bag_care():
    q = pricing.calculate_estimate([{"item_code": "BAG_CARE_STANDARD_HANDBAG", "quantity": 1}])
    assert q.lines[0].line_kind == "pending"
    assert q.lines[0].line_total is None
    assert q.subtotal_excluding_vat == 0.0


# --- Leather garments (founder 2026-08 docs: From price + inspection/photo) ---
def test_leather_jacket_resolves_and_is_starting_from():
    codes, reason = catalogue.resolve_item_alias("leather jacket")
    assert reason == "ok" and codes == ["LEATHER_JACKET"]
    rec = catalogue.item_by_code("LEATHER_JACKET")
    assert rec["current_price"] == 80
    assert rec["is_starting_price"] is True
    assert rec["requires_inspection"] is True


def test_leather_variants_present():
    for phrase, code, price in [
        ("leather trousers", "LEATHER_TROUSERS", 50),
        ("leather skirt", "LEATHER_SKIRT", 50),
        ("leather gloves", "LEATHER_GLOVES", 20),
    ]:
        codes, reason = catalogue.resolve_item_alias(phrase)
        assert reason == "ok" and codes == [code], (phrase, codes)
        assert catalogue.item_by_code(code)["current_price"] == price


def test_plain_jacket_still_clean_press_not_leather():
    # Adding leather must NOT hijack a bare "jacket".
    codes, _ = catalogue.resolve_item_alias("jacket")
    assert "LEATHER_JACKET" not in codes
