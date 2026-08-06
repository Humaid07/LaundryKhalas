"""Per-item detail builder — grounded, category-aware, never invents (Area 4)."""
from services import item_details as it


# ------------------------------- classify --------------------------------
def test_classify_covers_core_categories():
    assert it.classify_item({"name": "Wash & Fold"}) == "wash_fold"
    assert it.classify_item({"name": "Carpet — Regular"}) == "carpet"
    assert it.classify_item({"name": "Curtain (per panel)"}) == "curtain"
    assert it.classify_item({"name": "Oxford Shoe"}) == "shoe"
    assert it.classify_item({"name": "Designer Handbag"}) == "bag"
    assert it.classify_item({"name": "Suede Jacket"}) == "leather"
    assert it.classify_item({"name": "Shirt"}) == "garment"
    assert it.classify_item({"name": "Widget"}) == "other"


def test_classify_uses_order_service_for_alterations():
    assert it.classify_item({"name": "Trouser"}, "Alterations") == "alteration"


# --------------------------- wash & fold block ---------------------------
def test_wash_fold_block_present_only_when_grounded():
    d = it.build_item_detail(
        {"name": "Wash & Fold", "quantity": 1, "bags": 2, "estimated_weight": 7, "pricing_tier": "12kg"},
        index=0, order_service="Wash & Fold",
    )
    assert d["category"] == "wash_fold"
    assert d["wash_fold"] == {
        "bags": 2, "estimated_weight": 7, "confirmed_weight": None,
        "pricing_tier": "12kg", "separation_notes": None,
    }
    # No wash-fold fields → no block at all.
    d2 = it.build_item_detail({"name": "Wash & Fold", "quantity": 1}, index=0, order_service="Wash & Fold")
    assert "wash_fold" not in d2


# ---------------------------- dimension block ----------------------------
def test_carpet_dimension_block_estimated_vs_confirmed():
    d = it.build_item_detail(
        {"name": "Carpet", "measure": 30, "confirmed_sqm": 28.5, "rate_per_sqm": 12, "minimum_charge": 50},
        index=1, order_service="Carpet Cleaning",
    )
    assert d["category"] == "carpet"
    assert d["dimension"]["estimated_measure"] == 30
    assert d["dimension"]["confirmed_sqm"] == 28.5
    assert d["dimension"]["rate_per_sqm"] == 12
    assert d["dimension"]["minimum_charge"] == 50


# --------------------------- specialist block ----------------------------
def test_specialist_block_and_quotation_status_from_requires_quote():
    d = it.build_item_detail(
        {"name": "Leather Handbag", "material": "Calf leather", "repair_requirement": "Re-stitch handle",
         "requires_quote": True, "brand": "Prada", "designer": True},
        index=2, order_service="Bag Restoration",
    )
    assert d["category"] == "bag"
    assert d["specialist"]["material"] == "Calf leather"
    assert d["specialist"]["repair_requirement"] == "Re-stitch handle"
    assert d["specialist"]["quotation_status"] == "required"
    assert d["brand_candidate"] == "Prada"
    assert d["luxury_flag"] is True


def test_never_asserts_authenticity():
    import json
    d = it.build_item_detail(
        {"name": "Designer Handbag", "brand": "Chanel", "designer": True}, index=0)
    blob = json.dumps(d).lower()
    assert "authentic" not in blob and "counterfeit" not in blob and "genuine" not in blob


# ----------------------------- common fields -----------------------------
def test_common_fields_and_fee_photo_passthrough():
    d = it.build_item_detail(
        {"id": "li-9", "name": "Blue Shirt", "quantity": 3, "colour": "blue",
         "stains": "coffee on cuff", "instruction": "starch collar"},
        index=0, order_service="Dry Clean", fee=20.0, photo_count=2,
    )
    assert d["id"] == "li-9"
    assert d["quantity"] == 3
    assert d["colour"] == "blue"
    assert d["stains"] == "coffee on cuff"
    assert d["instruction"] == "starch collar"
    assert d["facility_fee"] == 20.0
    assert d["photo_count"] == 2


def test_string_item_falls_back_to_line_index_id():
    d = it.build_item_detail({"name": "X"}, index=4)
    assert d["id"] == "line-4"
