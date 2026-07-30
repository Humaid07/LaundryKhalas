"""Unit tests for the WhatsApp-agent enhancement (pure services).

Covers the decision logic of the required scenarios without a DB or network:
voice-note handling & escalation, structured order notes, WhatsApp identity,
location-pin capture, and the facility-handoff serializer.
"""

from __future__ import annotations

from channels.evolution_whatsapp import parse_evolution_webhook
from services import contact_identity as ci
from services import facility_handoff as fh
from services import location_capture as loc
from services import order_notes as notes
from services import voice_fallback as vf
from services.media_classification import MediaKind, classify_inbound_media


# --------------------------------------------------------------------------- #
# Media classification (scenario 1: detect audio before Claude)
# --------------------------------------------------------------------------- #

def test_classify_text_and_audio_and_location():
    assert classify_inbound_media({"conversation": "hello"}) is MediaKind.TEXT
    assert classify_inbound_media({"extendedTextMessage": {"text": "hi"}}) is MediaKind.TEXT
    assert classify_inbound_media({"audioMessage": {"ptt": True, "seconds": 3}}) is MediaKind.AUDIO
    assert classify_inbound_media({"pttMessage": {"seconds": 2}}) is MediaKind.AUDIO
    assert classify_inbound_media({"locationMessage": {"degreesLatitude": 25.1, "degreesLongitude": 55.2}}) is MediaKind.LOCATION
    assert classify_inbound_media({"imageMessage": {"caption": "x"}}) is MediaKind.IMAGE
    assert classify_inbound_media({}) is MediaKind.EMPTY


def test_audio_wins_even_inside_ephemeral_wrapper():
    wrapped = {"ephemeralMessage": {"message": {"audioMessage": {"ptt": True}}}}
    assert classify_inbound_media(wrapped) is MediaKind.AUDIO


def _evt(message: dict, mid: str = "M1") -> dict:
    return {"event": "messages.upsert", "data": {"messages": [{
        "key": {"remoteJid": "971502485658@s.whatsapp.net", "fromMe": False, "id": mid},
        "pushName": "Sara", "message": message,
    }]}}


def test_parser_keeps_audio_and_tags_media_kind():
    out = parse_evolution_webhook(_evt({"audioMessage": {"ptt": True}}, "AUD-1"))
    assert len(out) == 1
    assert out[0]["media_kind"] == "audio"
    assert out[0]["wa_message_id"] == "AUD-1"
    assert out[0]["text"] == ""  # never a hallucinated transcript


def test_parser_text_and_location_media_kind():
    t = parse_evolution_webhook(_evt({"conversation": "hi there"}))
    assert t[0]["media_kind"] == "text" and t[0]["text"] == "hi there"
    loc_out = parse_evolution_webhook(_evt({"locationMessage": {"degreesLatitude": 25.0, "degreesLongitude": 55.0, "name": "Marina"}}))
    assert loc_out[0]["media_kind"] == "location" and loc_out[0]["latitude"] == 25.0
    assert loc_out[0]["location_event"]["name"] == "Marina"


# --------------------------------------------------------------------------- #
# Voice fallback / escalation (scenarios 1-4)
# --------------------------------------------------------------------------- #

def test_first_voice_note_gets_one_text_fallback():
    d = vf.decide_voice_message(vf.VoiceState(), audio_message_id="AUDIO-1")
    assert d.action is vf.VoiceAction.FIRST_FALLBACK
    assert d.reply_text == vf.FALLBACK_TEXT
    assert d.new_count == 1
    assert d.new_status == vf.STATUS_FALLBACK_SENT
    assert d.escalation_reason is None


def test_duplicate_webhook_of_first_voice_is_ignored():
    state = vf.VoiceState(count=1, last_message_id="AUDIO-1", escalation_status=vf.STATUS_FALLBACK_SENT)
    d = vf.decide_voice_message(state, audio_message_id="AUDIO-1")
    assert d.action is vf.VoiceAction.DUPLICATE_IGNORED
    assert d.reply_text is None
    assert d.new_count == 1  # unchanged


def test_second_distinct_voice_note_escalates():
    state = vf.VoiceState(count=1, last_message_id="AUDIO-1", escalation_status=vf.STATUS_FALLBACK_SENT)
    d = vf.decide_voice_message(state, audio_message_id="AUDIO-2")
    assert d.action is vf.VoiceAction.ESCALATE
    assert d.should_escalate
    assert d.escalation_reason == vf.REPEATED_UNPROCESSABLE_VOICE_REASON
    assert d.reply_text == vf.HANDOVER_TEXT
    assert d.new_status == vf.STATUS_ESCALATED
    assert d.new_count == 2


def test_after_escalation_further_audio_is_held_no_reply():
    state = vf.VoiceState(count=2, last_message_id="AUDIO-2", escalation_status=vf.STATUS_ESCALATED)
    d = vf.decide_voice_message(state, audio_message_id="AUDIO-3")
    assert d.action is vf.VoiceAction.HOLD
    assert d.reply_text is None


def test_takeover_active_holds_even_first_audio():
    d = vf.decide_voice_message(vf.VoiceState(), audio_message_id="AUDIO-X", takeover_active=True)
    assert d.action is vf.VoiceAction.HOLD
    assert d.reply_text is None


def test_reset_state_on_valid_text():
    s = vf.reset_state()
    assert s.count == 0 and s.last_message_id is None and s.escalation_status == vf.STATUS_NONE


# --------------------------------------------------------------------------- #
# WhatsApp number + profile name (scenarios 17-20)
# --------------------------------------------------------------------------- #

def test_normalize_sender_number_to_e164():
    for raw in ("971502485658@s.whatsapp.net", "whatsapp:+971 50 248 5658", "971502485658:12@s.whatsapp.net"):
        e164, ok = ci.normalize_whatsapp_sender_number(raw)
        assert e164 == "+971502485658"
        assert ok is True


def test_normalize_sender_number_invalid():
    e164, ok = ci.normalize_whatsapp_sender_number("123")  # too short for E.164
    assert ok is False


def test_valid_profile_names_accepted():
    for name in ("Sara", "Mohammed Ali", "Zoya Khan", "Ben Smith", "أحمد", "أمينة", "José", "Mei Lin", "Sara Khan"):
        assert ci.validate_whatsapp_profile_name(name).valid, name


def test_invalid_profile_names_rejected():
    for name in ("iPhone", "Work Phone", "Unknown", "Laundry Customer", "Sales Team",
                 "Best Deals Dubai", "Best Deals Dubai 😊", "123456", "+971501234567",
                 "a@b.com", "http://x.com", "😊😊", ".", "", "  "):
        assert not ci.validate_whatsapp_profile_name(name).valid, name


def test_name_precedence_profile_used_without_asking():
    r = ci.resolve_customer_identity(whatsapp_profile_name="Sara Khan")
    assert r.name == "Sara Khan" and r.source == ci.SOURCE_WHATSAPP_PROFILE
    assert r.requires_confirmation is False


def test_name_precedence_invalid_profile_requires_ask():
    r = ci.resolve_customer_identity(whatsapp_profile_name="Best Deals Dubai")
    assert r.name is None and r.requires_confirmation is True and r.source == ci.SOURCE_UNKNOWN


def test_name_correction_customer_provided_wins():
    r = ci.resolve_customer_identity(explicit_name="Ahmed", whatsapp_profile_name="Mohammad")
    assert r.name == "Ahmed" and r.source == ci.SOURCE_CUSTOMER_PROVIDED


# --------------------------------------------------------------------------- #
# Structured order notes (scenarios 5-9)
# --------------------------------------------------------------------------- #

ORDER = "11111111-1111-1111-1111-111111111111"


def test_useful_note_validation_and_categories():
    v = notes.validate_order_note("PICKUP_INSTRUCTION", "Collect from reception.")
    assert v.ok and v.category == "PICKUP_INSTRUCTION"
    v2 = notes.validate_order_note("CONTACT_PREFERENCE", "Send a WhatsApp message when the driver arrives.")
    assert v2.ok


def test_irrelevant_statement_rejected():
    assert not notes.validate_order_note("OTHER_OPERATIONAL_NOTE", "Thanks, you are very helpful.").ok
    assert not notes.validate_order_note("OTHER_OPERATIONAL_NOTE", "thank you").ok


def test_unverified_promise_rejected():
    assert not notes.validate_order_note("TIMING_PREFERENCE", "Guaranteed delivery within two hours").ok
    # but storing the *request* is fine
    assert notes.validate_order_note("TIMING_PREFERENCE", "Customer requested delivery within two hours").ok


def test_duplicate_note_is_noop():
    existing = [{"id": "n1", "category": "PICKUP_INSTRUCTION", "text": "Collect from reception", "status": "ACTIVE",
                 "dedupe_key": notes.dedupe_key(ORDER, "PICKUP_INSTRUCTION", "Collect from reception")}]
    plan = notes.plan_note_merge(ORDER, existing, "PICKUP_INSTRUCTION", "collect from reception.")
    assert plan.action is notes.MergeAction.DUPLICATE


def test_contact_preference_correction_supersedes():
    existing = [{"id": "n1", "category": "CONTACT_PREFERENCE", "text": "Call me when the driver arrives", "status": "ACTIVE"}]
    plan = notes.plan_note_merge(ORDER, existing, "CONTACT_PREFERENCE", "Do not call, WhatsApp me instead")
    assert plan.action is notes.MergeAction.SUPERSEDE
    assert plan.supersedes_id == "n1"


def test_item_handling_notes_accumulate():
    existing = [{"id": "n1", "category": "ITEM_HANDLING", "text": "Keep white garments separate", "status": "ACTIVE"}]
    plan = notes.plan_note_merge(ORDER, existing, "ITEM_HANDLING", "Do not fold the suit")
    assert plan.action is notes.MergeAction.ADD


def test_patch_empty_never_erases():
    existing = [{"id": "n1", "category": "PICKUP_INSTRUCTION", "text": "Collect from reception", "status": "ACTIVE"}]
    assert notes.plan_patch(ORDER, existing, None) == []
    assert notes.plan_patch(ORDER, existing, []) == []


def test_removal_targets_only_matching_note():
    existing = [
        {"id": "n1", "category": "PICKUP_INSTRUCTION", "text": "Collect from reception", "status": "ACTIVE"},
        {"id": "n2", "category": "CONTACT_PREFERENCE", "text": "WhatsApp me on arrival", "status": "ACTIVE"},
    ]
    to_remove = notes.find_notes_to_remove(existing, target_text="reception")
    assert to_remove == ["n1"]


def test_grouping_and_snapshot():
    existing = [
        {"id": "n1", "category": "PICKUP_INSTRUCTION", "text": "Collect from reception", "status": "ACTIVE"},
        {"id": "n2", "category": "CONTACT_PREFERENCE", "text": "WhatsApp me on arrival", "status": "ACTIVE"},
        {"id": "n3", "category": "STAIN_NOTE", "text": "Blue shirt has a stain on the left sleeve", "status": "ACTIVE"},
        {"id": "n4", "category": "PICKUP_INSTRUCTION", "text": "removed one", "status": "REMOVED"},
    ]
    grouped = notes.group_active_by_category(existing)
    assert grouped["PICKUP_INSTRUCTION"] == ["Collect from reception"]
    assert "removed one" not in notes.summary_lines(existing)
    snap = notes.build_confirmed_snapshot(existing)
    assert len(snap) == 3 and all(s["category"] for s in snap)


# --------------------------------------------------------------------------- #
# Location pin + typed address (scenarios 13-16)
# --------------------------------------------------------------------------- #

def test_process_valid_location_event():
    cap = loc.process_whatsapp_location({"locationMessage": {"degreesLatitude": 25.077, "degreesLongitude": 55.139, "name": "Marina"}})
    assert cap.ok and cap.latitude == 25.077 and cap.longitude == 55.139
    assert cap.location_type == "static" and cap.location_name == "Marina"


def test_process_live_location_and_out_of_range():
    live = loc.process_whatsapp_location({"liveLocationMessage": {"degreesLatitude": 25.0, "degreesLongitude": 55.0}})
    assert live.ok and live.location_type == "live"
    bad = loc.process_whatsapp_location({"locationMessage": {"degreesLatitude": 999, "degreesLongitude": 55}})
    assert not bad.ok and bad.reason == "out_of_range"


def test_pin_without_address_reports_missing_fields():
    order = {"pickup_latitude": 25.0, "pickup_longitude": 55.0}
    assert loc.has_pin(order) and loc.pin_status(order) == loc.PIN_RECEIVED
    assert loc.missing_address_fields(order)  # building/apt/floor/room missing


def test_address_without_pin():
    order = {"pickup_address": "Apartment 1204, Marina Heights"}
    assert loc.has_typed_address(order)
    assert not loc.has_pin(order) and loc.pin_status(order) == loc.PIN_MISSING
    assert loc.missing_address_fields(order) == []  # don't nag when free-text present
    assert not loc.routing_ready(order)


def test_manual_review_pin_status_preserved():
    order = {"location_pin_status": "manual_review"}
    assert loc.pin_status(order) == loc.PIN_MANUAL_REVIEW
    assert not loc.routing_ready(order)


# --------------------------------------------------------------------------- #
# Facility handoff serializer (scenarios 11-12)
# --------------------------------------------------------------------------- #

def _order():
    return {
        "order_id": "LK-AE-2001", "service": "Wash and Fold", "service_name_snapshot": "Wash and Fold",
        "line_items": [{"name": "Shirt", "quantity": 3, "measure": "pieces"}],
        "pickup_date": "2026-08-01", "pickup_slot_label": "6 PM–8 PM",
        "pickup_latitude": 25.077, "pickup_longitude": 55.139, "location_type": "static",
        "pickup_address": "Apartment 1204, Marina Heights", "city": "Dubai", "pickup_area": "Dubai Marina",
        # fields that must NEVER leak:
        "margin_amount": 42.5, "customer_tier": "Gold", "payout_rate": 0.6, "amount": 120,
    }


def _active_notes():
    return [
        {"id": "n1", "category": "PICKUP_INSTRUCTION", "text": "Collect from reception", "status": "ACTIVE"},
        {"id": "n2", "category": "STAIN_NOTE", "text": "Blue shirt stain on sleeve", "status": "ACTIVE"},
    ]


def _customer():
    return {"customer_name": "Sara Khan", "normalized_contact_number": "+971502485658", "phone_e164": "+971502485658"}


def test_handoff_includes_allowed_and_excludes_internal():
    payload = fh.build_facility_handoff_payload(
        order=_order(), active_notes=_active_notes(), customer=_customer(), share=fh.FacilityShareConfig()
    )
    assert payload["order_id"] == "LK-AE-2001"
    assert payload["items"][0]["quantity"] == 3
    assert payload["notes"]["pickup_instructions"] == ["Collect from reception"]
    assert payload["notes"]["stains_and_damage"] == ["Blue shirt stain on sleeve"]
    assert payload["location_pin"]["latitude"] == 25.077
    assert payload["customer_name"] == "Sara Khan"
    assert payload["customer_whatsapp_number"] == "+971502485658"
    # internal / financial fields never present
    blob = str(payload)
    for leaked in ("margin", "tier", "payout", "Gold", "0.6"):
        assert leaked not in blob.lower() if leaked.islower() else leaked not in blob


def test_handoff_privacy_config_omits_disabled_fields_but_keeps_routing():
    share = fh.FacilityShareConfig(customer_name=False, customer_phone=False, typed_address=False, location_pin=True)
    payload = fh.build_facility_handoff_payload(
        order=_order(), active_notes=_active_notes(), customer=_customer(), share=share
    )
    assert "customer_name" not in payload
    assert "customer_whatsapp_number" not in payload
    assert "pickup_address" not in payload
    # routing still works: coarse area/city retained + pin present
    assert payload["pickup_area"] == "Dubai Marina" and payload["city"] == "Dubai"
    assert payload["location_pin"]["latitude"] == 25.077
