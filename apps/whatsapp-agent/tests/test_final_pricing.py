"""Final customer pricing: published prices are ALREADY VAT-inclusive, so the
customer pays the stored price with NO 5% added, computed with Decimal math, and
NO VAT/tax wording ever appears on a customer surface (task spec §§1-4, tests
1-12).
"""
from decimal import Decimal

import pytest

from services import catalogue, money, pricing


# --- Decimal money utility: published price is final, unchanged (spec §§1-3) --
@pytest.mark.parametrize("base", [60, 80, 7, 9, 11, 20, 50])
def test_final_unit_price_never_adds_vat(base):
    got = money.final_unit_price(base, vat_rate=0.05)     # default: inclusive
    assert got == money.round_money(base)                 # 60 -> 60, 9 -> 9
    assert isinstance(got, Decimal)                       # Decimal, never binary float


@pytest.mark.parametrize("base, final", [(60, "60"), (80, "80"), (9, "9"), (50, "50")])
def test_published_price_is_the_customer_price(base, final):
    got = money.final_unit_price(base, vat_rate=0.05)
    assert money.format_money(got) == final               # spec §1 examples verbatim


def test_legacy_exclusive_branch_still_available_but_unused():
    # The add-5% branch is retained only for completeness; no live catalogue uses
    # it. Explicitly asking for it still adds — but the DEFAULT never does.
    assert money.final_unit_price(60, vat_rate=0.05, prices_include_vat=False) == Decimal("63.00")
    assert money.final_unit_price(60, vat_rate=0.05) == Decimal("60.00")


def test_line_total_is_per_unit_price_times_quantity():
    # spec §6: final unit price (unchanged) × quantity.
    assert money.final_line_total(9, 3, vat_rate=0.05) == Decimal("27.00")
    assert money.final_line_total(11, 2, vat_rate=0.05) == Decimal("22.00")


def test_vat_breakdown_is_internal_and_reconciles():
    # Internal accounting only: split the tax OUT of an inclusive total (never
    # adds to the customer price). 60 inclusive -> net 57.14 + tax 2.86 == 60.
    net, tax = money.vat_breakdown(Decimal("60.00"), vat_rate=0.05)
    assert net + tax == Decimal("60.00")
    assert net == Decimal("57.14") and tax == Decimal("2.86")


@pytest.mark.parametrize("value, shown", [
    (Decimal("60.00"), "60"), (Decimal("80.00"), "80"), (Decimal("9.00"), "9"),
    (Decimal("7.35"), "7.35"), (Decimal("88.40"), "88.40"), (Decimal("52.50"), "52.50"),
])
def test_format_money_whole_vs_decimal(value, shown):
    assert money.format_money(value) == shown


# --- Quote engine: final totals + no VAT wording ----------------------------
def test_multi_item_order_total_sums_final_line_totals():
    # 3 shirts (9) + 2 trousers (11) -> 27 + 22 = 49, no 5% added.
    q = pricing.calculate_estimate([
        {"item_code": "CLEAN_PRESS_SHIRT", "quantity": 3},
        {"item_code": "CLEAN_PRESS_TROUSERS", "quantity": 2},
    ])
    assert q.customer_total == 49.0
    assert q.estimated_total_including_vat == 49.0
    totals = {ln.item_code: ln.line_total for ln in q.lines}
    assert totals["CLEAN_PRESS_SHIRT"] == 27.0
    assert totals["CLEAN_PRESS_TROUSERS"] == 22.0


def test_customer_summary_and_lines_never_mention_vat():
    q = pricing.calculate_estimate([{"item_code": "CLEAN_PRESS_SHIRT", "quantity": 3}])
    summary = pricing.format_quote_summary(q)
    lines = " ".join(pricing.format_quote_lines(q))
    for banned in ("VAT", "vat", "Tax", "tax", "excl", "incl", "Subtotal", "subtotal"):
        assert banned not in summary, banned
        assert banned not in lines, banned
    assert "AED 27" in summary


def test_item_price_label_is_final_and_vat_free():
    # 6 kg Wash & Fold bag: catalogue price 60 -> customer label AED 60 (spec §1).
    item = None
    for it in catalogue.all_items():
        if it.get("current_price") == 60 and (it.get("pricing_unit") or "").lower() == "bag":
            item = it
            break
    if item is None:
        pytest.skip("no 60/bag item in the catalogue")
    label = catalogue.item_price_label(item)
    assert "60" in label and "63" not in label
    assert "VAT" not in label and "vat" not in label


def test_starting_price_label_uses_final_value():
    # Sneakers price 50 -> 'From AED 50 …' (spec §1), never 52.50.
    item = catalogue.item_by_code("SHOE_CARE_SPORTS_SNEAKERS")
    if not item:
        pytest.skip("no sneakers item")
    label = catalogue.item_price_label(item)
    assert "50" in label and "52.50" not in label
    assert label.lower().startswith("from")


def test_prices_are_inclusive_by_default_no_double_application():
    q = pricing.calculate_estimate([{"item_code": "CLEAN_PRESS_SHIRT", "quantity": 1}])
    # catalogue price 9 is already final -> 9.00, not 9.45; no 5% is added.
    assert q.lines[0].unit_price == 9.0
    assert q.customer_total == 9.0
