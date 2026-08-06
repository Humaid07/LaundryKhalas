"""Per-item detail builder for the facility order view (pure, grounded).

Turns one confirmed line item into the rich, category-aware DTO the facility
dashboard renders: common attributes (name, quantity, colour, brand candidate,
material, stains, existing damage, special handling, measurements, price type,
inspection/quote status, fee, photos) plus a category-specific block for
Wash & Fold (bags/weight/tier), carpets & curtains (estimated vs confirmed sqm,
rate, minimum charge) and specialist work (shoes/bags/leather/restoration).

Every field is read from a structured line-item key — nothing is invented. When a
key is absent the field is simply omitted (None), and the UI shows only what is
grounded. We never assert an item is authentic or counterfeit; ``luxury_flag`` is
only echoed from an explicit data flag.
"""

from __future__ import annotations

# Category → the substrings (in the item/service text) that identify it. Order
# matters: the first match wins, so put specific categories before generic ones.
_CATEGORY_SIGNALS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("wash_fold", ("wash and fold", "wash & fold", "washfold", "laundry bag", "by weight", "per kg")),
    ("carpet", ("carpet", "rug")),
    ("curtain", ("curtain", "drape", "blind")),
    ("shoe", ("shoe", "sneaker", "trainer", "boot")),
    ("bag", ("handbag", "purse", "wallet", "backpack")),
    ("leather", ("leather", "suede")),
    ("alteration", ("alteration", "tailor", "shorten", "hem", "take in", "let out", "resize", "repair")),
    ("garment", ("shirt", "trouser", "dress", "suit", "jacket", "abaya", "kandura", "coat", "blouse", "skirt")),
)


def _clean(value) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    s = str(value).strip()
    return s or None


def _num(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    try:
        f = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return int(f) if f == int(f) else f


def _first(item: dict, *keys: str):
    for k in keys:
        v = item.get(k)
        if v is not None and (not isinstance(v, str) or v.strip()):
            return v
    return None


def classify_item(item: dict, order_service: str = "") -> str:
    """Grounded category key for one item, from its own + the order's service text."""
    text = " ".join(
        str(item.get(k, "")) for k in
        ("name", "canonical_name", "item_code", "category", "service", "service_code",
         "service_display", "pricing_type")
    )
    text = f"{text} {order_service}".lower()
    for category, signals in _CATEGORY_SIGNALS:
        if any(sig in text for sig in signals):
            return category
    return "other"


def _wash_fold_block(item: dict) -> dict | None:
    block = {
        "bags": _num(_first(item, "bags", "bag_count", "number_of_bags")),
        "estimated_weight": _num(_first(item, "estimated_weight", "customer_weight", "weight_estimate")),
        "confirmed_weight": _num(_first(item, "confirmed_weight", "facility_weight", "actual_weight")),
        "pricing_tier": _clean(_first(item, "pricing_tier", "tier", "bag_tier")),
        "separation_notes": _clean(_first(item, "separation_notes", "separation", "sorting_notes")),
    }
    return block if any(v is not None for v in block.values()) else None


def _dimension_block(item: dict) -> dict | None:
    block = {
        "estimated_measure": _num(_first(item, "estimated_measure", "customer_measure", "measure")),
        "confirmed_sqm": _num(_first(item, "confirmed_sqm", "facility_sqm", "actual_sqm")),
        "rate_per_sqm": _num(_first(item, "rate_per_sqm", "rate", "sqm_rate")),
        "minimum_charge": _num(_first(item, "minimum_charge", "min_charge", "minimum")),
        "measurement_status": _clean(_first(item, "measurement_status", "measure_status")),
    }
    return block if any(v is not None for v in block.values()) else None


def _specialist_block(item: dict, requires_quote: bool) -> dict | None:
    block = {
        "material": _clean(_first(item, "material", "fabric")),
        "cleaning_requirement": _clean(_first(item, "cleaning_requirement", "cleaning", "treatment")),
        "repair_requirement": _clean(_first(item, "repair_requirement", "repair", "restoration")),
        "inspection_status": _clean(_first(item, "inspection_status", "inspection")),
        "quotation_status": _clean(_first(item, "quotation_status", "quote_status"))
                            or ("required" if requires_quote else None),
    }
    return block if any(v is not None for v in block.values()) else None


def build_item_detail(
    item: dict,
    *,
    index: int,
    order_service: str = "",
    order_status: str | None = None,
    fee: float | None = None,
    photo_count: int = 0,
) -> dict:
    """Full, category-aware per-item DTO. Only grounded fields are populated."""
    category = classify_item(item, order_service)
    item_id = str(_first(item, "id", "item_code") or f"line-{index}")
    name = _first(item, "name", "canonical_name", "item", "item_code") or "Item"
    requires_quote = bool(item.get("requires_quote"))
    inspection_required = bool(
        item.get("inspection_required")
        or _clean(_first(item, "inspection_status", "inspection"))
    )

    detail = {
        "id": item_id,
        "name": str(name),
        "category": category,
        "category_label": _first(item, "category", "catalogue_category_name"),
        "quantity": _num(item.get("quantity")),
        "measure": _num(item.get("measure")),
        "service": _first(item, "service_display", "service", "service_name") or order_service,
        "service_subtype": _clean(_first(item, "service_subtype", "service_code")),
        "instruction": _clean(_first(item, "instruction", "alteration", "adjustment", "work_instruction")),
        "colour": _clean(_first(item, "colour", "color")),
        "brand_candidate": _clean(_first(item, "brand_candidate", "brand")),
        "luxury_flag": bool(_first(item, "luxury", "is_luxury", "designer", "is_designer")),
        "material": _clean(_first(item, "material", "fabric")),
        "stains": _clean(_first(item, "stains", "stain_note", "stain")),
        "existing_damage": _clean(_first(item, "existing_damage", "damage", "damage_note")),
        "special_handling": _clean(_first(item, "special_handling", "special_care", "care")),
        "measurements": _clean(_first(item, "measurements", "dimensions")),
        "price_type": _clean(_first(item, "price_type", "pricing_type")),
        "turnaround": _clean(_first(item, "turnaround", "turnaround_text")),
        "requires_quote": requires_quote,
        "inspection_required": inspection_required,
        "facility_fee": fee,
        "photo_count": int(photo_count or 0),
        "item_status": _clean(_first(item, "status", "item_status")) or order_status,
    }

    if category == "wash_fold":
        block = _wash_fold_block(item)
        if block:
            detail["wash_fold"] = block
    elif category in ("carpet", "curtain"):
        block = _dimension_block(item)
        if block:
            detail["dimension"] = block
    elif category in ("shoe", "bag", "leather"):
        block = _specialist_block(item, requires_quote)
        if block:
            detail["specialist"] = block

    return detail
