"""Wash & Fold weight optimiser (services/wash_fold_pricing, ruleset 2026_08_05).

Anchors the published examples and the removal of the old AED 7 per-kg rule:
  6 kg → 60, 12 kg → 90, 13 kg → 102, 18 kg → 150, 20 kg → 180, 24 kg → 180.
"""
from decimal import Decimal

import pytest

from services import catalogue, wash_fold_pricing as wf


@pytest.fixture(autouse=True)
def _fresh():
    catalogue.reload_catalogue()
    yield
    catalogue.reload_catalogue()


def _total(kg, market="AE"):
    return wf.optimize_wash_fold(kg, market=market).total


# --- published example matrix (AED) -----------------------------------------
@pytest.mark.parametrize("kg,expected", [
    (1, 60),     # below 6 kg still one 6 kg package
    (6, 60),
    (7, 90),     # 6.1–12 kg band → 12 kg package (never 6 kg + additional)
    (12, 90),
    (13, 102),   # 12 kg package + 1 additional kg (90 + 12)
    (18, 150),   # 12 kg + 6 kg package (90 + 60)
    (20, 180),   # two 12 kg packages (90 + 90)
    (24, 180),   # two 12 kg packages exactly
])
def test_published_wash_fold_totals(kg, expected):
    assert _total(kg) == Decimal(expected)


def test_no_seven_per_kg_rule_anywhere():
    # The old AED 7 additional-kg rule is gone: 13 kg must be 102 (90 + 12), never
    # 90 + 7 = 97 or 60 + 7*7 = 109.
    q = wf.optimize_wash_fold(13)
    assert q.price_additional_kg == Decimal(12)
    assert q.total == Decimal(102)
    assert catalogue.item_by_code("WASH_FOLD_ADDITIONAL_KG")["current_price"] == 12
    assert catalogue.item_by_code("WASH_FOLD_12KG")["current_price"] == 90


def test_breakdown_shape_for_13kg():
    q = wf.optimize_wash_fold(13)
    assert q.packages_12kg == 1 and q.additional_kg == 1 and q.packages_6kg == 0
    assert q.currency == "AED"
    assert q.ruleset_version == "2026_08_05"


def test_fractional_remainder_rounds_up_additional_kg():
    # 12.4 kg → one 12 kg package + additional weight rounded up to 1 kg.
    q = wf.optimize_wash_fold(12.4)
    assert q.packages_12kg == 1 and q.additional_kg == 1
    assert q.total == Decimal(90) + Decimal(12)


def test_qatar_uses_qar_and_same_band_math():
    q = wf.optimize_wash_fold(13, market="QA")
    assert q.currency == "QAR"
    assert q.total == Decimal(102)   # QAR 90 + 12, same bands as AED


def test_rejects_non_positive_weight():
    with pytest.raises(ValueError):
        wf.optimize_wash_fold(0)
