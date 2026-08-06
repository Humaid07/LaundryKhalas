"""Canonical facility issue-type registry (Area 5)."""
from services import facility_issue_types as it


def test_all_spec_types_present():
    for key in (
        "ITEM_DIFFERS_FROM_DESCRIPTION", "PHOTO_REQUIRED", "MEASUREMENT_REQUIRED",
        "SPECIALIST_TREATMENT_REQUIRED", "EXISTING_DAMAGE_DETECTED", "HEAVY_STAIN_DETECTED",
        "MATERIAL_REQUIRES_REVIEW", "ALTERATION_CLARIFICATION_REQUIRED", "ALTERATION_PHOTO_REQUIRED",
        "ALTERATION_NOT_STANDARD", "ALTERATION_TECHNICIAN_REVIEW", "PRICE_REVISION_REQUIRED",
        "SERVICE_NOT_SUPPORTED", "ADDITIONAL_PROCESSING_REQUIRED", "UNABLE_TO_MEET_TURNAROUND",
        "MISSING_ITEM", "WRONG_ITEM_RECEIVED", "OTHER",
    ):
        assert key in it.KEYS


def test_resolve_sets_flags_from_registry():
    spec = it.resolve("PRICE_REVISION_REQUIRED")
    assert spec.requires_price_revision is True
    assert spec.requires_customer_response is True
    assert spec.blocking is True
    assert spec.priority == "urgent"


def test_photo_required_flags_photo_not_price():
    spec = it.resolve("PHOTO_REQUIRED")
    assert spec.requires_photo is True
    assert spec.requires_price_revision is False
    assert spec.blocking is False


def test_legacy_aliases_map_to_canonical():
    assert it.normalize_key("damage") == "EXISTING_DAMAGE_DETECTED"
    assert it.normalize_key("missing") == "MISSING_ITEM"
    assert it.normalize_key("delay") == "UNABLE_TO_MEET_TURNAROUND"
    assert it.normalize_key("alteration_price_change") == "ALTERATION_NOT_STANDARD"


def test_unknown_defaults_to_other():
    assert it.normalize_key("nonsense") == "OTHER"
    assert it.resolve(None).key == "OTHER"


def test_catalogue_shape():
    cat = it.catalogue()
    assert len(cat) == len(it.KEYS)
    row = next(r for r in cat if r["key"] == "MISSING_ITEM")
    assert row["severity"] == "critical" and row["blocking"] is True
