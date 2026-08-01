"""WhatsApp-agent behaviour matrix (spec §17) — DETERMINISTIC, offline coverage.

Every scenario is asserted at the service / pure-function layer (no live LLM, no
DB, no network), mirroring how the rest of the suite verifies the agent. Where a
scenario is ALREADY covered elsewhere it is referenced rather than duplicated:

  * emoji / dash normalisation .............. tests/test_reply_style.py
  * memory shaping + masking + isolation .... tests/test_customer_memory.py
  * persona wording / no-virtual-assistant .. tests/test_agent_prompt_persona.py
  * base identity + location parsing ........ tests/test_voice_notes_identity_location.py

This file adds the §17 assertions those files do NOT already make: the process /
services question surfaces, the name-precedence branches end to end, the
returning-customer memory pin re-ask, the typed-address-vs-pin gap matrix, the
no-fabricated-coordinates guarantee, the order-summary surfaces (name / service /
pickup / address / pin status / order id / emoji-free), and the prompt contract.

Any scenario that genuinely needs the model's generated reply is asserted against
the deterministic backend rule that governs it (the prompt contract in §14 /
test 10), not a flaky live-LLM call.
"""
from __future__ import annotations

import datetime as _dt

import pytest

import rules
from agents.whatsapp_agent.booking_tools import (
    booking_system_prompt,
    workflow_state_block,
)
from api import evolution_webhooks as webhooks
from services import contact_identity as ci
from services import customer_memory as mem
from services import location_capture as loc
from services.reply_style import normalize_customer_reply

# A tiny emoji sample used to prove customer-facing text is emoji-free.
_EMOJI_SAMPLE = ("😀", "✅", "🧺", "👍", "📍", "🚚", "❤", "⭐")


# =========================================================================== #
# §17.2 — Services question: catalogue is config/DB-driven, not a stale list
# =========================================================================== #
# (That the booking prompt does NOT dump the service list on a greeting is
#  already asserted by test_agent_prompt_persona.test_no_emojis_and_no_service_list_on_greeting.)

def test_active_service_catalogue_is_nonempty_and_config_driven():
    active = rules.active_service_catalog()
    assert active, "active service catalogue must not be empty"
    # Derived from the full configured catalogue (a filtered view of it), never a
    # hardcoded parallel list — every active entry is one of the configured ones.
    full = rules.service_catalog()
    assert all(s in full for s in active)
    # Only genuinely-active services are offered.
    assert all(s.get("active", True) for s in active)


def test_service_options_accessor_is_config_driven():
    opts = rules.service_options()
    assert opts, "service_options must not be empty"
    # One option per active service, carrying the config label/id (not invented).
    assert len(opts) == len(rules.active_service_catalog())
    labels = {s["label"] for s in rules.active_service_catalog()}
    assert all(o["label"] in labels and o["id"] for o in opts)


# =========================================================================== #
# §17.3 — Valid WhatsApp number is the contact; the agent never asks for it
# =========================================================================== #
# (Base E.164 normalisation is covered by test_voice_notes_identity_location;
#  here we assert the returning-customer implication: number is known, masked,
#  and not a field the agent must collect.)

def test_valid_sender_number_normalized_and_never_asked():
    e164, ok = ci.normalize_whatsapp_sender_number("971502485658@s.whatsapp.net")
    assert (e164, ok) == ("+971502485658", True)
    # The resolved contact number is surfaced to the agent MASKED, so the agent has
    # it and never needs to ask — and the raw number never enters model context.
    cust = {"id": "c-num", "masked_phone": "+9715••••⁘58",
            "phone_e164": e164, "customer_name": "Sara", "customer_name_source": "CONFIRMED"}
    ctx = mem.build_returning_customer_context(cust)
    assert ctx["whatsapp_number"] == cust["masked_phone"]
    assert e164 not in str(ctx)  # raw number is never in the model-facing block


# =========================================================================== #
# §17.4 — Name precedence: explicit > confirmed > valid profile > ask
# =========================================================================== #

def test_name_precedence_explicit_wins_over_everything():
    r = ci.resolve_customer_identity(
        explicit_name="Ahmed", confirmed_name="Old Name", whatsapp_profile_name="Sara Khan")
    assert r.name == "Ahmed"
    assert r.source == ci.SOURCE_CUSTOMER_PROVIDED
    assert r.requires_confirmation is False


def test_name_precedence_confirmed_used_when_no_explicit():
    r = ci.resolve_customer_identity(
        confirmed_name="Zoya Khan", whatsapp_profile_name="Sara Khan")
    assert r.name == "Zoya Khan"
    assert r.source == ci.SOURCE_CONFIRMED
    assert r.requires_confirmation is False


def test_name_precedence_valid_profile_used_without_asking():
    r = ci.resolve_customer_identity(whatsapp_profile_name="Sara Khan")
    assert r.name == "Sara Khan"
    assert r.source == ci.SOURCE_WHATSAPP_PROFILE
    assert r.requires_confirmation is False


def test_name_precedence_invalid_profile_forces_ask():
    # A device/slogan/low-confidence profile name is rejected → agent must ask.
    for bad in ("iPhone", "Best Deals Dubai", "Laundry Customer", "123456"):
        assert ci.validate_whatsapp_profile_name(bad).valid is False, bad
        r = ci.resolve_customer_identity(whatsapp_profile_name=bad)
        assert r.name is None
        assert r.source == ci.SOURCE_UNKNOWN
        assert r.requires_confirmation is True


# =========================================================================== #
# §17.5-8 — Returning-customer memory: saved typed address re-asks the pin
# =========================================================================== #
# (Confirmed-name greeting + masking are covered by test_customer_memory; here we
#  add the pin implication: a saved TYPED address with no coordinates must NOT
#  claim a pin — so the agent re-asks the location pin for this order.)

_RETURNING = {
    "id": "44444444-4444-4444-4444-444444444444",
    "masked_phone": "+9715••••⁘09",
    "phone_e164": "+971582003209",
    "customer_name": "Zoya",
    "customer_name_source": "CUSTOMER_CONFIRMED",
}


def test_returning_customer_with_saved_typed_address_has_no_pin():
    saved = {"typed_address": "Apartment 1204, Marina Heights, Dubai Marina",
             "area": "Dubai Marina", "city": "Dubai"}  # no coordinates persisted
    ctx = mem.build_returning_customer_context(
        _RETURNING, confirmed_name="Zoya", saved_address=saved)
    assert ctx["returning_customer"] is True
    assert ctx["customer_name"] == "Zoya"
    sa = ctx["saved_address"]
    assert sa["typed_address"].startswith("Apartment 1204")
    # Location pins are NOT stored between orders → pin_available False → re-ask.
    assert sa["pin_available"] is False
    assert sa["latitude"] is None and sa["longitude"] is None


# =========================================================================== #
# §17.11 — Typed address present but no pin: ask only for the pin
# =========================================================================== #

def test_typed_address_without_pin_is_not_routing_ready():
    order = {"pickup_address": "Apartment 1204, Marina Heights, Dubai Marina"}
    assert loc.has_typed_address(order) is True
    assert loc.has_pin(order) is False
    assert loc.routing_ready(order) is False          # needs the pin to route
    assert loc.pin_status(order) == loc.PIN_MISSING
    assert loc.missing_address_fields(order) == []    # don't nag for unit fields


# =========================================================================== #
# §17.12 — Pin present but typed address missing: ask only for unit detail
# =========================================================================== #

def test_pin_without_typed_address_reports_missing_unit_fields():
    order = {"pickup_latitude": 25.077, "pickup_longitude": 55.139}
    assert loc.has_pin(order) is True
    assert loc.routing_ready(order) is True           # pin is enough to route
    assert loc.pin_status(order) == loc.PIN_RECEIVED
    assert loc.has_typed_address(order) is False
    missing = loc.missing_address_fields(order)
    assert missing, "unit detail (building/floor/apartment/room) must be requested"


# =========================================================================== #
# §17.12 — Invalid / stale pin: coordinates are NEVER fabricated
# =========================================================================== #

@pytest.mark.parametrize("event", [
    None,
    {},
    {"locationMessage": {}},                                            # no coords
    {"locationMessage": {"degreesLatitude": 25.0}},                     # half coords
    {"locationMessage": {"degreesLatitude": 999, "degreesLongitude": 55}},   # out of range
    {"locationMessage": {"degreesLatitude": 25.0, "degreesLongitude": 500}}, # out of range
])
def test_invalid_location_never_fabricates_coordinates(event):
    cap = loc.process_whatsapp_location(event)
    assert cap.ok is False
    assert cap.latitude is None and cap.longitude is None  # nothing invented


# =========================================================================== #
# §17.13 — Order summary surfaces: name / service / pickup / address / pin / id
# =========================================================================== #

def _confirmed_row() -> dict:
    return {
        "order_id": "LK-AE-1024",
        "conversation_state": "READY_TO_CONFIRM",
        "status": "draft",
        "customer_name": "Sara Khan",
        "service_id": "wash_and_fold",
        "service": "Wash & Fold",
        "service_name_snapshot": "Wash & Fold",
        "service_display_name": "Wash & Fold",
        "line_items": [{"item_code": "WF-STD", "name": "Mixed laundry", "quantity": 1,
                        "line_kind": "priced"}],
        "estimated_total": 63, "pricing_is_estimated": False,
        "pickup_date": _dt.date(2026, 8, 2), "pickup_slot": "6 PM to 8 PM",
        "pickup_address": "Apartment 1204, Marina Heights, Dubai Marina",
        "pickup_area": "Dubai Marina",
        "pickup_instruction_text": None,
    }


def test_workflow_summary_surfaces_name_service_pickup_address():
    block = workflow_state_block(_confirmed_row())
    # Name is surfaced as the confirmed customer name (order reference).
    assert block["customer"]["confirmed_name"] == "Sara Khan"
    # Service, pickup date, pickup window and address are all present.
    assert block["order"]["service_category"] == "Wash & Fold"
    assert block["order"]["pickup_date"] == "2026-08-02"
    assert block["order"]["pickup_time_window"] == "6 PM to 8 PM"
    assert block["order"]["pickup_address_present"] is True
    assert block["order"]["pickup_area"] == "Dubai Marina"
    assert block["order_number"] == "LK-AE-1024"
    assert block["ready_to_confirm"] is True  # nothing missing


def test_order_summary_shows_location_pin_status():
    # The pin status shown in the summary comes from the same deterministic helper
    # get_order_summary uses; a draft with no coordinates reports MISSING (re-ask).
    row_no_pin = _confirmed_row()
    assert loc.pin_status(row_no_pin) == loc.PIN_MISSING
    row_with_pin = {**_confirmed_row(), "pickup_latitude": 25.077, "pickup_longitude": 55.139}
    assert loc.pin_status(row_with_pin) == loc.PIN_RECEIVED


def test_final_confirmation_text_is_concise_has_id_and_no_emoji():
    text = webhooks._final_confirmation_text(_confirmed_row())
    # Concise (a short block, not a report).
    assert len(text.splitlines()) <= 12
    # Order id + the key summary fields.
    assert "LK-AE-1024" in text
    assert "Service:" in text
    assert "Wash & Fold" in text
    assert "Pickup date:" in text
    assert "Pickup time:" in text
    assert "Address:" in text
    assert "Apartment 1204, Marina Heights, Dubai Marina" in text
    # No emoji at all.
    for e in _EMOJI_SAMPLE:
        assert e not in text
    assert normalize_customer_reply(text).emoji_count == 0


def test_final_confirmation_text_shows_name_and_pin_status():
    # §13: the summary renders the customer Name and the Location pin status.
    text_no_pin = webhooks._final_confirmation_text(_confirmed_row())
    assert "Name: Sara Khan" in text_no_pin
    assert "Location pin: Not received" in text_no_pin
    row_with_pin = {**_confirmed_row(), "pickup_latitude": 25.077, "pickup_longitude": 55.139}
    assert "Location pin: Received" in webhooks._final_confirmation_text(row_with_pin)


# =========================================================================== #
# §17.14 — Prompt contract (deterministic string assertions)
# =========================================================================== #
# (Persona / no-virtual-assistant is covered by test_agent_prompt_persona; here
#  we assert the returning-customer + style clauses that govern the generated
#  reply for scenarios that cannot be asserted deterministically otherwise.)

def test_booking_prompt_contract():
    bp = booking_system_prompt()
    low = bp.lower()
    # Facility wording — never the absolute nearest.
    assert "one of the nearest suitable facilities" in low
    # No emojis instruction.
    assert "no emojis" in low
    assert "never use emojis" in low
    # Short replies instruction. (The prompt states the brevity rule qualitatively
    # — "short"/"concise" — after commit 6c6a2b0 replaced the numeric "50 words".)
    assert "short repl" in low
    assert "concise" in low
    # Returning customers must reshare the location pin (pins not stored between orders).
    assert "reshare" in low
    assert "location pin" in low


# =========================================================================== #
# §17.17 — Memory isolation between two different customers
# =========================================================================== #
# (test_customer_memory.test_memory_isolation_between_customers already covers
#  this; we add one more asserting two independently-built blocks share NO field
#  values, as a second guard that memory never bleeds across conversations.)

def test_two_customer_blocks_never_share_identity_or_address():
    a = mem.build_returning_customer_context(
        _RETURNING, confirmed_name="Zoya",
        saved_address={"typed_address": "Apartment 1204, Marina Heights", "area": "Dubai Marina"})
    other = {
        "id": "55555555-5555-5555-5555-555555555555",
        "masked_phone": "+9715••••⁘60",
        "phone_e164": "+971502485658",
        "customer_name": "Sam",
        "customer_name_source": "CUSTOMER_PROVIDED",
    }
    b = mem.build_returning_customer_context(other, confirmed_name="Sam")
    assert a["customer_id"] != b["customer_id"]
    assert a["whatsapp_number"] != b["whatsapp_number"]
    # None of A's identity or address text appears in B's block.
    assert "Zoya" not in str(b)
    assert "Marina Heights" not in str(b)
    # B carried no saved address, so it must not have one fabricated.
    assert "saved_address" not in b
