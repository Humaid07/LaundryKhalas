from app.services.privacy import (
    customer_context_for_llm,
    facility_facing_order_view,
    mask_email,
    mask_phone,
    mask_pii,
)


def test_mask_phone_removes_numbers():
    text = "Please call me at +971 50 123 4567 to confirm."
    masked = mask_phone(text)
    assert "123 4567" not in masked
    assert "[phone redacted]" in masked


def test_mask_email_removes_addresses():
    text = "My email is jane.doe@example.com, reach out anytime."
    masked = mask_email(text)
    assert "jane.doe@example.com" not in masked
    assert "[email redacted]" in masked


def test_mask_pii_removes_both():
    text = "Call +971501234567 or email jane@example.com"
    masked = mask_pii(text)
    assert "+971501234567" not in masked
    assert "jane@example.com" not in masked


def test_customer_context_for_llm_excludes_pii():
    ctx = customer_context_for_llm(
        name="Jane",
        area="Marina",
        city="Dubai",
        preferred_language="en",
    )
    serialized = str(ctx)
    assert "phone" not in serialized.lower() or "phone_number" not in ctx
    assert "@" not in serialized
    assert ctx["area_city"] == "Marina, Dubai"


def test_facility_facing_order_view_excludes_contact_details():
    order = {
        "order_id": "abc-123",
        "service_type": "wash_and_fold",
        "items": {"service_type": "wash_and_fold"},
        "area": "Marina",
        "city": "Dubai",
        "address_text": "Apt 12, Marina Towers, Dubai Marina",
        "customer_phone": "+971501234567",
        "customer_email": "jane@example.com",
    }
    view = facility_facing_order_view(order)
    assert "customer_phone" not in view
    assert "customer_email" not in view
    assert "address_text" not in view
    assert view["area"] == "Marina"
