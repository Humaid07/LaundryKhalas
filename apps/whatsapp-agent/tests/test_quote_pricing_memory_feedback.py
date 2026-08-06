"""Quote pricing/markup + feedback detection + memory PATCH policy (Areas B/C)."""
from services import quote_pricing as qp
from services import customer_feedback as fb
from services import customer_memory_store as mem


# ------------------------------ markup calc ------------------------------
def test_markup_percentage_snapshot():
    snap = qp.calculate_customer_price_from_facility_quote(
        100, margin_rule={"margin_type": "percentage", "margin_value": 40})
    assert snap["customer_subtotal"] == 140.0
    assert snap["final_customer_price"] == 140.0
    assert snap["facility_fee"] == 100.0  # internal; never sent to customer by the presenter


def test_markup_with_discount_and_surcharges():
    snap = qp.calculate_customer_price_from_facility_quote(
        100, margin_rule={"margin_type": "percentage", "margin_value": 50},
        discount_percentage=10, delivery_charge=10, express_surcharge=20)
    # subtotal 150; discount 15; +10 +20 = 165
    assert snap["customer_subtotal"] == 150.0
    assert snap["discount_amount"] == 15.0
    assert snap["final_customer_price"] == 165.0


def test_default_margin_used_when_no_rule():
    snap = qp.calculate_customer_price_from_facility_quote(100, margin_rule=None)
    assert snap["final_customer_price"] == 130.0  # 30% default


# --------------------------- operations review ---------------------------
def test_high_value_requires_review():
    snap = {"facility_fee": 200, "final_customer_price": 350}
    required, reasons = qp.requires_operations_review(snap)
    assert required and "ABOVE_AMOUNT_THRESHOLD" in reasons


def test_wedding_and_restoration_require_review():
    snap = {"facility_fee": 50, "final_customer_price": 120}
    r1, reasons1 = qp.requires_operations_review(snap, wedding=True)
    assert r1 and "WEDDING_DRESS" in reasons1
    r2, reasons2 = qp.requires_operations_review(snap, restoration=True)
    assert r2 and "RESTORATION" in reasons2


def test_normal_quote_no_review():
    snap = {"facility_fee": 50, "final_customer_price": 120}   # 58% margin, under 300
    required, reasons = qp.requires_operations_review(snap)
    assert required is False and reasons == []


# ------------------------------ feedback ---------------------------------
def test_name_correction_is_customer_scope():
    got = fb.detect_feedback("My name is Zoya, not Zoha")
    assert any(e["feedback_type"] == fb.NAME_CORRECTION and e["scope"] == fb.CUSTOMER for e in got)


def test_contact_preference_customer_scope():
    got = fb.detect_feedback("Do not call me, WhatsApp only")
    assert any(e["feedback_type"] == fb.CONTACT_PREFERENCE and e["scope"] == fb.CUSTOMER for e in got)


def test_too_long_is_global():
    got = fb.detect_feedback("Your replies are always too long")
    assert any(e["feedback_type"] == fb.NEGATIVE_RESPONSE_FEEDBACK and e["scope"] == fb.GLOBAL for e in got)


def test_price_wrong_is_global():
    got = fb.detect_feedback("The price you gave is wrong")
    assert any(e["feedback_type"] == fb.PRICE_FEEDBACK and e["scope"] == fb.GLOBAL for e in got)


def test_another_order_is_order_scope():
    got = fb.detect_feedback("This is for another order")
    assert any(e["feedback_type"] == fb.ORDER_ASSOCIATION_CORRECTION for e in got)


def test_for_this_order_forces_order_scope():
    assert fb.classify_scope(fb.CONTACT_PREFERENCE, "collect from reception for this order") == fb.ORDER


# --------------------------- memory PATCH policy -------------------------
def test_null_never_erases():
    plan = mem.plan_memory_write([], memory_key="address", memory_value=None, customer_confirmed=True)
    assert plan["action"] == "reject" and plan["reason"] == "null_never_erases"


def test_unconfirmed_guess_is_not_stored():
    plan = mem.plan_memory_write([], memory_key="name", memory_value="Zoya", customer_confirmed=False)
    assert plan["action"] == "reject" and plan["reason"] == "not_customer_confirmed"


def test_new_confirmed_memory_saves():
    plan = mem.plan_memory_write([], memory_key="name", memory_value="Zoya", customer_confirmed=True)
    assert plan["action"] == "save"


def test_correction_supersedes():
    existing = [{"id": "m1", "memory_key": "address", "scope": mem.CUSTOMER_GLOBAL,
                 "memory_value": "Apartment 403", "status": "active"}]
    plan = mem.plan_memory_write(existing, memory_key="address", memory_value="Apartment 904",
                                 scope=mem.CUSTOMER_GLOBAL, customer_confirmed=True)
    assert plan["action"] == "supersede" and plan["supersede_id"] == "m1"


def test_unchanged_is_noop():
    existing = [{"id": "m1", "memory_key": "name", "scope": mem.CUSTOMER_GLOBAL,
                 "memory_value": "Zoya", "status": "active"}]
    plan = mem.plan_memory_write(existing, memory_key="name", memory_value="zoya ",
                                 scope=mem.CUSTOMER_GLOBAL, customer_confirmed=True)
    assert plan["action"] == "noop"


def test_scope_resolution_and_isolation():
    assert mem.resolve_scope("I always use the Marina address") == mem.CUSTOMER_GLOBAL
    assert mem.resolve_scope("collect from reception for this order") == mem.ORDER_ONLY
    assert mem.influences_other_orders(mem.ORDER_ONLY) is False
    assert mem.influences_other_orders(mem.CUSTOMER_GLOBAL) is True
