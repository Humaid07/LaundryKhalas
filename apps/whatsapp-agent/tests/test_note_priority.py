"""Note priority classifier — critical operational info stands out (Area 1)."""
from services import note_priority as np


def test_explicit_priority_wins():
    assert np.classify("PICKUP_INSTRUCTION", "ring bell", explicit="CRITICAL") == "CRITICAL"
    assert np.classify("PICKUP_INSTRUCTION", "ring bell", explicit="IMPORTANT") == "IMPORTANT"


def test_explicit_normal_falls_through_to_derivation():
    # A stored NORMAL is the default; derivation still applies.
    assert np.classify("EXISTING_DAMAGE", "small tear on collar", explicit="NORMAL") == "IMPORTANT"


def test_existing_damage_is_important_by_category():
    assert np.classify("EXISTING_DAMAGE", "scuff on the toe") == "IMPORTANT"


def test_do_not_process_is_critical():
    assert np.classify("FACILITY_INSTRUCTION", "Do not process until approved") == "CRITICAL"
    assert np.is_critical("ITEM_HANDLING", "do not alter the waist") is True


def test_allergy_is_critical():
    assert np.classify("SPECIAL_CARE", "customer has a chemical allergy") == "CRITICAL"


def test_luxury_keywords_are_important():
    assert np.classify("ITEM_HANDLING", "designer leather handbag, handle with care") == "IMPORTANT"


def test_plain_pickup_note_is_normal():
    assert np.classify("PICKUP_INSTRUCTION", "collect from reception") == "NORMAL"


def test_normalize_priority_coerces_junk():
    assert np.normalize_priority("nonsense") == "NORMAL"
    assert np.normalize_priority(None) == "NORMAL"
    assert np.normalize_priority("critical") == "CRITICAL"
