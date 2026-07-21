import pytest

from agents.whatsapp_agent import tools


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Dry cleaning in JVC", "JVC"),
        ("pickup from JLT please", "JLT"),
        ("I'm near JBR", "JBR"),
        ("Dubai Marina", "Dubai Marina"),
        ("collect from Al Nahda", "Al Nahda"),
        ("in Doha", "Doha"),
    ],
)
def test_extract_area_recognizes_short_forms_and_full_names(text, expected):
    assert tools.extract_area(text) == expected


def test_extract_area_fallback_catches_unlisted_capitalized_place():
    # A made-up community name not in the gazetteer at all - a capitalized
    # phrase following a preposition should still be picked up.
    assert tools.extract_area("pickup from Greenview Residences") == "Greenview Residences"


def test_extract_area_fallback_does_not_false_positive_on_time_words():
    assert tools.extract_area("I need pickup in the Morning") is None
    assert tools.extract_area("see you Tomorrow") is None


@pytest.mark.parametrize(
    "text,expected",
    [
        ("dubi marina", "Dubai Marina"),
        ("I'm in Bussiness Bay", "Business Bay"),
        ("near Al Barha", "Al Barsha"),
        ("pickup from Dowtown Dubai", "Downtown Dubai"),
    ],
)
def test_extract_area_tolerates_typos(text, expected):
    assert tools.extract_area(text) == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("I'm in Marina", "Dubai Marina"),
        ("near Downtown", "Downtown Dubai"),
        ("pickup from Barsha", "Al Barsha"),
        ("office is in DIFC", "DIFC"),
        ("I'm at MBZ City", "MBZ City"),
        ("collect from Khalifa City", "Khalifa City"),
        ("pickup in Al Hamra", "Al Hamra"),
        ("I'm in Al Wakrah", "Al Wakrah"),
    ],
)
def test_extract_area_covers_all_emirates_and_common_aliases(text, expected):
    assert tools.extract_area(text) == expected


@pytest.mark.parametrize(
    "text",
    ["What time do you open?", "How much is dry cleaning", "Can you pick up today?", "Do you deliver?"],
)
def test_is_question_detects_question_phrasing(text):
    assert tools.is_question(text) is True


@pytest.mark.parametrize("text", ["yes", "Yes!", "yeah", "sure", "okay", "go ahead"])
def test_is_affirmative(text):
    assert tools.is_affirmative(text) is True


@pytest.mark.parametrize("text", ["no", "nope", "not now", "no thanks"])
def test_is_negative(text):
    assert tools.is_negative(text) is True


def test_detect_intent_confirmation_and_unanswerable():
    assert tools.detect_intent("yes") == "confirmation_yes"
    assert tools.detect_intent("no thanks") == "confirmation_no"
    assert tools.detect_intent("Do you use eco-friendly detergent?") == "unanswerable_question"
