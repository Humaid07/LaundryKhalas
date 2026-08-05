"""Centralized service-rule registry (services/service_rules, spec §17)."""
import pytest

from services import catalogue
from services import service_rules as sr


@pytest.fixture(autouse=True)
def _fresh():
    catalogue.reload_catalogue()
    yield
    catalogue.reload_catalogue()


def test_exact_item_shirt():
    r = sr.resolve_rule("CLEAN_PRESS_SHIRT")
    assert r.pricing_mode == sr.EXACT
    assert r.base_price == 9
    assert r.express_eligible is True          # Clean & Press is express-eligible (§19)
    assert r.discount_eligible is True
    assert r.photo_required is False and r.facility_quote_required is False
    assert r.rule_version == "2026_08_05"


def test_wash_fold_bag_is_exact_and_express():
    r = sr.resolve_rule("WASH_FOLD_6KG")
    assert r.pricing_mode == sr.EXACT and r.express_eligible is True


def test_additional_kg_is_weight_confirmed():
    r = sr.resolve_rule("WASH_FOLD_ADDITIONAL_KG")
    assert r.pricing_mode == sr.WEIGHT_CONFIRMED
    assert r.measurement_required is True


def test_curtain_is_measured_with_minimum_not_express():
    r = sr.resolve_rule("HOME_CARE_CURTAIN_SQM")
    assert r.pricing_mode == sr.MEASURED
    assert r.minimum_charge == 50
    assert r.express_eligible is False
    assert r.measurement_required is True


def test_sole_replacement_is_facility_quote():
    r = sr.resolve_rule("RESTORATION_SOLE_REPLACEMENT")
    assert r.pricing_mode == sr.FACILITY_QUOTE
    assert r.facility_quote_required is True
    assert r.base_price is None
    assert r.discount_eligible is False        # no discount on an unknown total (§15.6)
    assert r.photo_required is True            # restoration category


def test_designer_sneakers_from_price_and_photo():
    r = sr.resolve_rule("SHOE_CARE_DESIGNER_SNEAKERS")
    assert r.pricing_mode == sr.FROM
    assert r.photo_required is True            # 'designer' keyword
    assert r.express_eligible is False
    assert r.discount_eligible is False        # a 'From' price is not discountable


def test_unknown_item_returns_none():
    assert sr.resolve_rule("NOPE_NOT_A_CODE") is None
