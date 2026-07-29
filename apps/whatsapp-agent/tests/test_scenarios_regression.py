"""Stage 6 — §12 regression scenarios (built from the real-chat behaviours).

Each test maps to one numbered scenario in the founder spec §12 and asserts the
RULE-level behaviour through the real backend engines (pricing, negotiation,
delivery/express, routing, complaints, privacy) or the agent's system prompt (the
agent's behavioural contract). No LLM, no DB — deterministic.
"""
from __future__ import annotations

import datetime as _dt
from decimal import Decimal

from agents.whatsapp_agent.booking_tools import booking_system_prompt, workflow_state_block
from services import booking_flow as bf
from services import (
    catalogue,
    complaints,
    delivery,
    negotiation,
    pricing,
    service_resolution,
    specialty_routing,
)

PROMPT = booking_system_prompt()


# 1) Wash & Fold quote — VAT-inclusive website price, 24h, nothing invented.
def test_s1_wash_fold_quote_vat_inclusive_and_24h():
    q = pricing.calculate_estimate([{"item_code": "WASH_FOLD_6KG", "quantity": 1}])
    assert q.prices_include_vat is True
    assert q.customer_total > 0
    assert not q.discount_applied              # full price by default (negotiation-only)
    t = delivery.order_turnaround(["WASH_FOLD_6KG"])
    assert (t["min_hours"], t["max_hours"]) == (24, 24)


# 2) Haggle < 100 — 10% → 20% → facility-floor (itemised) → escalate below it.
def test_s2_haggle_under_100_ladder_and_floor():
    assert negotiation.plan_offer(60).percentage == Decimal("10")
    assert negotiation.plan_offer(60, current_percentage=Decimal("10")).percentage == Decimal("20")
    floor = negotiation.plan_offer(60, current_percentage=Decimal("20"),
                                   itemised=True, facility_cost=Decimal("30"))
    assert floor.action == "offer_floor" and floor.price == Decimal("34.50")
    # Not itemised → cannot go below the standard max; ask for the item list.
    assert negotiation.plan_offer(60, current_percentage=Decimal("20"),
                                  itemised=False, facility_cost=Decimal("30")).action == "ask_itemisation"


# 3) Haggle >= 100 — 15% → 25% → escalate beyond the floor.
def test_s3_haggle_over_100_ladder():
    assert negotiation.plan_offer(200).percentage == Decimal("15")
    assert negotiation.plan_offer(200, current_percentage=Decimal("15")).percentage == Decimal("25")
    beyond = negotiation.plan_offer(200, current_percentage=Decimal("42.5"),
                                    current_rule_code="NEG_FLOOR")
    assert beyond.action == "escalate"


# 4) Express after 3 PM — not rejected; facility capacity check, standard fallback.
def test_s4_express_after_cutoff_not_rejected():
    q = delivery.express_quote(["WASH_FOLD_6KG"], 100, _dt.datetime(2026, 7, 29, 16, 30))
    assert q.eligible is True and q.requires_facility_check is True
    assert "standard" in PROMPT.lower() and "quote_express" in PROMPT


# 5) Specialty photo-gate — request a photo before quoting specialty items.
def test_s5_specialty_photo_gate_in_prompt():
    assert "PHOTO before any quote" in PROMPT
    assert "do not quote a specialty item from description alone" in PROMPT


# 6) Address capture — booking not confirmable without address + name.
def test_s6_address_and_name_required_before_confirm():
    row = {"order_id": "LK-1", "conversation_state": bf.WAITING_FOR_SERVICE,
           "line_items": [{"item_code": "WASH_FOLD_6KG", "name": "Wash & Fold", "quantity": 1}]}
    block = workflow_state_block(row)
    assert "pickup_address" in block["missing_fields"]
    assert "customer_name" in block["missing_fields"]
    assert block["ready_to_confirm"] is False
    assert "building/villa/flat number" in PROMPT and "room number for hotels" in PROMPT


# 7) Slot honesty — present only tool-returned windows; never invent availability.
def test_s7_slot_honesty_in_prompt():
    assert "Present ONLY the returned available_slots" in PROMPT or \
           "Show ONLY windows returned by get_available_pickup_slots" in PROMPT
    assert "Never invent availability" in PROMPT


# 8) Payment — push card, allow cash, never a driver side-deal.
def test_s8_payment_rules_in_prompt():
    assert "prefer secure online card payment" in PROMPT
    assert "cash on" in PROMPT
    assert "NEVER arrange cash off-system directly with the driver" in PROMPT


# 9) Complaint — classified, escalated; the agent never promises a refund.
def test_s9_complaint_classified_no_refund_promise():
    cat = complaints.classify_category("my shirt came back with a burn mark", None)
    assert cat  # a real complaint category is assigned
    assert "NEVER promise a refund, replacement or compensation" in PROMPT
    assert "REFUNDS require a human" in PROMPT


# 10) B2B / villa / wedding / bespoke — captured + routed, never quoted.
def test_s10_route_to_specialist_categories():
    assert specialty_routing.classify("villa deep cleaning").category == "HOME_CLEANING"
    assert specialty_routing.classify("clean my wedding dress").category == "WEDDING_DRESS"
    assert specialty_routing.classify("re-dye my couture jacket").category == "LUXURY_BESPOKE"
    res = service_resolution.classify_service_request("wedding dress")
    assert res.kind is service_resolution.ServiceKind.ROUTE and res.is_supported is False


# 11) Alteration — sample garment or exact measurements; confirm cm vs inch.
def test_s11_alterations_measurements_in_prompt():
    assert "sample garment OR exact measurements" in PROMPT
    assert "cm or inches" in PROMPT


# 12) Privacy — the model-facing state block never exposes the full address.
def test_s12_state_block_hides_full_address():
    row = {"order_id": "LK-1", "conversation_state": bf.WAITING_FOR_CONFIRMATION,
           "pickup_address": "Villa 12, Al Barsha 2", "pickup_area": "Al Barsha"}
    block = workflow_state_block(row)
    assert block["order"]["pickup_address_present"] is True
    assert "Villa 12" not in str(block)


# 13) Promo suppression — no review/promo while a complaint is open.
def test_s13_promo_suppressed_during_complaint():
    assert "NEVER send a review request" in PROMPT
    assert "while a complaint or" in PROMPT


# 14) Arabic — reply naturally in the customer's language.
def test_s14_arabic_language_instruction():
    assert "Arabic" in PROMPT


# Sanity: the catalogue actually backs scenario 1's item.
def test_scenario_items_exist_in_catalogue():
    assert catalogue.item_by_code("WASH_FOLD_6KG") is not None
