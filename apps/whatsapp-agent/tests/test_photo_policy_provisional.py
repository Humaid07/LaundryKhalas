"""Photo policy (5 levels) + provisional pricing presenter (Area A)."""
from services import service_rules as sr
from services import provisional_pricing as pp


# ------------------------------ photo policy -----------------------------
def test_standard_exact_is_not_required():
    assert sr.derive_photo_policy(mode=sr.EXACT, category="ALTERATIONS",
                                  item_code_low="trouser_shortening", specialist=False) == sr.PHOTO_NOT_REQUIRED


def test_specialist_facility_quote_needs_photo_for_remote_exact():
    assert sr.derive_photo_policy(mode=sr.FACILITY_QUOTE, category="BAG_CARE",
                                  item_code_low="designer_bag", specialist=True) == sr.PHOTO_REQUIRED_FOR_REMOTE_EXACT_QUOTE


def test_specialist_from_is_recommended():
    assert sr.derive_photo_policy(mode=sr.FROM, category="LEATHER",
                                  item_code_low="leather_jacket", specialist=True) == sr.PHOTO_RECOMMENDED


def test_non_specialist_from_is_optional():
    assert sr.derive_photo_policy(mode=sr.FROM, category="WASH_FOLD",
                                  item_code_low="wash_fold", specialist=False) == sr.PHOTO_OPTIONAL


def test_photo_never_blocks_pickup():
    for policy in sr.PHOTO_POLICIES:
        assert sr.photo_blocks_pickup(policy) is False


def test_should_request_photo_levels():
    assert sr.should_request_photo(sr.PHOTO_RECOMMENDED) is True
    assert sr.should_request_photo(sr.PHOTO_REQUIRED_FOR_REMOTE_EXACT_QUOTE) is True
    assert sr.should_request_photo(sr.PHOTO_REQUIRED_BEFORE_PROCESSING) is True
    assert sr.should_request_photo(sr.PHOTO_OPTIONAL) is False
    assert sr.should_request_photo(sr.PHOTO_NOT_REQUIRED) is False


# --------------------------- provisional pricing -------------------------
def test_state_from_mode():
    assert pp.state_from_mode(sr.EXACT) == pp.PUBLISHED_EXACT
    assert pp.state_from_mode(sr.FROM) == pp.PUBLISHED_FROM
    assert pp.state_from_mode(sr.RANGE) == pp.PUBLISHED_RANGE
    assert pp.state_from_mode(sr.FACILITY_QUOTE) == pp.AWAITING_FACILITY_QUOTE
    assert pp.state_from_mode(sr.WEIGHT_CONFIRMED) == pp.PROVISIONAL_ESTIMATE


def test_provisional_vs_final_classification():
    assert pp.is_provisional(pp.AWAITING_FACILITY_QUOTE) is True
    assert pp.is_provisional(pp.PUBLISHED_FROM) is True
    assert pp.is_final(pp.CUSTOMER_PRICE_SENT) is True
    assert pp.is_final(pp.AWAITING_FACILITY_QUOTE) is False


def test_published_exact_wording():
    s = pp.present_price(pp.PUBLISHED_EXACT, exact=40, item_label="Trouser shortening")
    assert s == "Trouser shortening is AED 40."


def test_published_from_wording():
    s = pp.present_price(pp.PUBLISHED_FROM, minimum=80, item_label="Leather jacket cleaning")
    assert "starts from AED 80" in s


def test_published_range_wording():
    s = pp.present_price(pp.PUBLISHED_RANGE, minimum=150, maximum=500, item_label="Wedding dress cleaning")
    assert "around AED 150 to AED 500" in s and "depending on the item" in s


def test_provisional_estimate_never_called_final():
    s = pp.present_price(pp.PROVISIONAL_ESTIMATE, exact=100)
    assert "estimated price" in s.lower()
    assert "confirm the exact amount after inspection" in s
    assert "final" not in s.lower()


def test_awaiting_facility_quote_wording():
    s = pp.present_price(pp.AWAITING_FACILITY_QUOTE)
    assert "confirm the exact price after the facility checks it" in s


def test_facility_confirmed_price_is_final_with_one_question():
    s = pp.present_price(pp.CUSTOMER_PRICE_SENT, exact=140)
    assert "final price is AED 140" in s and "Shall I proceed?" in s


def test_order_summary_price_line_provisional_and_final():
    assert pp.order_summary_price_line(pp.AWAITING_FACILITY_QUOTE) == "Price: To be confirmed after facility inspection."
    assert "from AED 80" in pp.order_summary_price_line(pp.AWAITING_FACILITY_QUOTE, minimum=80)
    assert pp.order_summary_price_line(pp.CUSTOMER_PRICE_SENT, exact=140) == "Price: AED 140"
