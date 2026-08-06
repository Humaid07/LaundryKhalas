"""Central facility order-view serializer — payload contract + privacy (Area 1)."""
from services import facility_order_view as view
from services.facility_handoff import FacilityShareConfig


def _order():
    return {
        "id": "uuid-1",
        "order_id": "LK-AE-1024",
        "status": "picked_up",
        "service_display_name": "Alterations",
        "service_id": "svc-alt",
        "line_items": [
            {"id": "li-1", "name": "Trouser", "quantity": 2, "instruction": "Reduce length by 4 cm"},
        ],
        "pickup_date": "2026-08-07",
        "pickup_start_time": "09:00",
        "pickup_end_time": "11:00",
        "estimated_delivery_end_at": "2026-08-09T18:00:00",
        "turnaround_text": "48 hours",
        # internal / customer fields that MUST NOT surface:
        "amount": 120,
        "stripe_hosted_invoice_url": "https://pay.stripe.example/x",
        "customer_phone": "+971501234567",
        "pickup_address": "Villa 12, Marina",
    }


def _notes():
    return [
        {"id": "n1", "category": "ITEM_HANDLING", "text": "Do not alter the waist", "status": "ACTIVE"},
        {"id": "n2", "category": "PICKUP_INSTRUCTION", "text": "Ring the bell twice", "status": "ACTIVE"},
        {"id": "n3", "category": "EXISTING_DAMAGE", "text": "small scuff on hem", "status": "ACTIVE",
         "is_amendment": True},
    ]


def _share():
    return FacilityShareConfig(customer_name=True, customer_phone=True, typed_address=True, location_pin=True)


def _build(**over):
    kwargs = dict(
        order=_order(), active_notes=_notes(), notes_all=_notes(), photos=[],
        issues=[], fee_snapshot=None, review=None, share=_share(), customer=None,
    )
    kwargs.update(over)
    return view.build_facility_order_view(**kwargs)


# --------------------------- required work -------------------------------
def test_required_work_summary_is_grounded():
    out = _build()
    assert out["order"]["required_work_summary"] == ["Alter 2 Trousers — Reduce length by 4 cm"]


# --------------------------- notes + priority ----------------------------
def test_notes_grouped_with_priority_and_critical_surfaced():
    out = _build()
    assert "item_handling" in out["notes"]
    assert out["notes"]["item_handling"][0]["priority"] == "CRITICAL"  # "do not alter"
    assert out["notes"]["pickup_instructions"][0]["priority"] == "NORMAL"
    # critical list is a flat convenience for the card header.
    assert any(n["text"] == "Do not alter the waist" for n in out["critical_notes"])
    # amendment collected under its own section.
    assert any(n["is_amendment"] for n in out["notes"]["amendments"])


# --------------------------- privacy firewall ----------------------------
def test_no_internal_or_customer_financials_leak():
    import json
    blob = json.dumps(_build(fee_snapshot={"facility_cost": 40, "currency": "AED", "complete": True}))
    for forbidden in ("stripe", "margin", "120", "+971501234567"):
        assert forbidden not in blob.lower()
    # finance shows ONLY facility fee + payout.
    fin = _build(fee_snapshot={"facility_cost": 40, "currency": "AED", "complete": True})["facility_finance"]
    assert fin["fee_total"] == 40.0
    assert fin["currency"] == "AED"
    assert "margin" not in fin and "customer_amount" not in fin


def test_customer_fields_omitted_when_share_disabled():
    off = FacilityShareConfig(customer_name=False, customer_phone=False, typed_address=False, location_pin=False)
    out = _build(share=off, customer={"customer_name": "Aisha", "normalized_contact_number": "+9715..."})
    assert "name" not in out["customer"]
    assert "phone" not in out["customer"]
    assert "typed_address" not in out["location"]


def test_customer_fields_present_when_share_enabled():
    out = _build(customer={"customer_name": "Aisha", "normalized_contact_number": "+97150"})
    assert out["customer"]["name"] == "Aisha"
    assert out["customer"]["phone"] == "+97150"


# --------------------------- photos --------------------------------------
def test_photos_split_by_item_and_general_with_source_inference():
    photos = [
        {"id": "p1", "order_item_id": "li-1", "stage": "intake", "content_type": "image/jpeg"},
        {"id": "p2", "order_item_id": None, "stage": "pre_dispatch"},
        {"id": "p3", "order_item_id": "li-1", "stage": "customer_reference", "source": "CUSTOMER"},
    ]
    block = _build(photos=photos)["photos"]
    assert block["count"] == 3
    assert len(block["general"]) == 1
    assert len(block["by_item"]["li-1"]) == 2
    # source inferred from stage when not explicit.
    p1 = next(p for p in block["all"] if p["id"] == "p1")
    assert p1["source"] == "FACILITY_BEFORE_PROCESSING"
    p3 = next(p for p in block["all"] if p["id"] == "p3")
    assert p3["source"] == "CUSTOMER"  # explicit wins
    # never leak a storage key.
    assert all("storage_key" not in p for p in block["all"])


# --------------------------- versions + review ack -----------------------
def test_compute_versions_monotonic_on_notes_and_photos():
    v = view.compute_versions(notes_all=_notes(), photo_count=2)
    assert v["notes_version"] == 3
    assert v["photo_version"] == 2
    assert v["order_version"] == 1  # one amendment note


def test_review_ack_required_when_absent():
    ack = _build(review=None)["review_acknowledgement"]
    assert ack["acknowledged"] is False and ack["up_to_date"] is False and ack["required"] is True


def test_review_ack_up_to_date_when_versions_match():
    current = view.compute_versions(notes_all=_notes(), photo_count=0)
    review = {"notes_version": current["notes_version"], "photo_version": current["photo_version"],
              "order_version": current["order_version"], "acknowledged_at": "t0", "invalidated_at": None}
    out = _build(review=review)
    assert out["review_acknowledgement"]["up_to_date"] is True


def test_review_ack_stale_when_a_note_was_added():
    # Acknowledged against 2 notes; order now has 3 → stale with a reason.
    review = {"notes_version": 2, "photo_version": 0, "order_version": 0,
              "acknowledged_at": "t0", "invalidated_at": None}
    ack = _build(review=review)["review_acknowledgement"]
    assert ack["up_to_date"] is False
    assert "notes updated" in ack["invalidation_reason"]


# --------------------------- actions -------------------------------------
def test_start_processing_gated_until_review_acknowledged():
    # picked_up + no review → start_cleaning present but DISABLED.
    actions = _build(review=None)["available_actions"]
    start = next(a for a in actions if a["action"] == "start_cleaning")
    assert start["enabled"] is False and start["requires_ack"] is True
    assert any(a["action"] == "acknowledge_review" for a in actions)


def test_start_processing_enabled_after_ack():
    current = view.compute_versions(notes_all=_notes(), photo_count=0)
    review = {**current, "acknowledged_at": "t0", "invalidated_at": None}
    out = _build(review=review)
    start = next(a for a in out["available_actions"] if a["action"] == "start_cleaning")
    assert start["enabled"] is True
    assert out["next_action"]["action"] == "start_cleaning"


def test_completed_order_has_no_processing_actions():
    order = _order()
    order["status"] = "completed"
    out = _build(order=order)
    assert out["available_actions"] == []
    assert out["next_action"] is None
