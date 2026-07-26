"""Final customer pricing: the 5% adjustment is ALWAYS included in customer-
facing prices, applied exactly once with Decimal math, and NO VAT/tax wording
ever appears on a customer surface (task spec §§17-24, tests 36-52).
"""
from decimal import Decimal

import pytest

from services import catalogue, money, pricing


# --- Decimal money utility (spec §19) ---------------------------------------
@pytest.mark.parametrize("base, final", [
    (60, "63.00"), (80, "84.00"), (7, "7.35"), (9, "9.45"), (11, "11.55"),
    (20, "21.00"), (50, "52.50"),
])
def test_final_unit_price_adds_five_percent(base, final):
    got = money.final_unit_price(base, vat_rate=0.05)
    assert got == Decimal(final)
    assert isinstance(got, Decimal)              # Decimal, never binary float


def test_prices_already_inclusive_are_not_adjusted_again():
    # spec §18: prices_include_vat=True → the stored price is already final.
    assert money.final_unit_price(63, vat_rate=0.05, prices_include_vat=True) == Decimal("63.00")


def test_line_total_is_per_unit_rounded_then_multiplied():
    # spec §20: final unit price rounded first, then × quantity.
    assert money.final_line_total(9, 3, vat_rate=0.05) == Decimal("28.35")
    assert money.final_line_total(11, 2, vat_rate=0.05) == Decimal("23.10")


def test_vat_breakdown_is_internal_and_reconciles():
    net, tax = money.vat_breakdown(Decimal("63.00"), vat_rate=0.05)
    assert net == Decimal("60.00") and tax == Decimal("3.00")
    assert net + tax == Decimal("63.00")


@pytest.mark.parametrize("value, shown", [
    (Decimal("63.00"), "63"), (Decimal("84.00"), "84"), (Decimal("21.00"), "21"),
    (Decimal("7.35"), "7.35"), (Decimal("9.45"), "9.45"), (Decimal("52.50"), "52.50"),
])
def test_format_money_whole_vs_decimal(value, shown):
    assert money.format_money(value) == shown


# --- Quote engine: final totals + no VAT wording ----------------------------
def test_multi_item_order_total_sums_final_line_totals():
    # 3 shirts (9) + 2 trousers (11) → 28.35 + 23.10 = 51.45 (spec §23 example)
    q = pricing.calculate_estimate([
        {"item_code": "CLEAN_PRESS_SHIRT", "quantity": 3},
        {"item_code": "CLEAN_PRESS_TROUSERS", "quantity": 2},
    ])
    assert q.customer_total == 51.45
    assert q.estimated_total_including_vat == 51.45
    totals = {ln.item_code: ln.line_total for ln in q.lines}
    assert totals["CLEAN_PRESS_SHIRT"] == 28.35
    assert totals["CLEAN_PRESS_TROUSERS"] == 23.10


def test_customer_summary_and_lines_never_mention_vat():
    q = pricing.calculate_estimate([{"item_code": "CLEAN_PRESS_SHIRT", "quantity": 3}])
    summary = pricing.format_quote_summary(q)
    lines = " ".join(pricing.format_quote_lines(q))
    for banned in ("VAT", "vat", "Tax", "tax", "excl", "incl", "Subtotal", "subtotal"):
        assert banned not in summary, banned
        assert banned not in lines, banned
    assert "AED 28.35" in summary


def test_item_price_label_is_final_and_vat_free():
    # 6 kg Wash & Fold bag: catalogue base 60 → customer label AED 63 (spec §22).
    item = None
    for it in catalogue.all_items():
        if it.get("current_price") == 60 and (it.get("pricing_unit") or "").lower() == "bag":
            item = it
            break
    if item is None:
        pytest.skip("no 60/bag item in the catalogue")
    label = catalogue.item_price_label(item)
    assert "63" in label and "VAT" not in label and "vat" not in label


def test_starting_price_label_uses_final_value():
    # Sneakers base 50 → 'From AED 52.50 …' (spec §21).
    item = catalogue.item_by_code("SHOE_CARE_SPORTS_SNEAKERS")
    if not item:
        pytest.skip("no sneakers item")
    label = catalogue.item_price_label(item)
    assert "52.50" in label and label.lower().startswith("from")


def test_no_double_application_when_catalogue_marks_inclusive(monkeypatch):
    monkeypatch.setattr(catalogue, "prices_include_vat", lambda: True)
    q = pricing.calculate_estimate([{"item_code": "CLEAN_PRESS_SHIRT", "quantity": 1}])
    # base 9 already 'final' → 9.00, not 9.45; the 5% is NOT applied again.
    assert q.lines[0].unit_price == 9.0
    assert q.customer_total == 9.0
