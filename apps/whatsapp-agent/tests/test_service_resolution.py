"""Authoritative service-request classifier (services/service_resolution.py).

Deterministic + offline: proves the BACKEND decides whether a service is
supported — valid/alias/ambiguous/bespoke/unsupported — so the agent can never
be tricked into offering (or re-asking for) something.
"""
from services import service_resolution as sr
from services.service_resolution import ServiceKind as K


def _kind(text, **kw):
    return sr.classify_service_request(text, **kw).kind


def test_valid_services_and_aliases_resolve_to_a_catalogue_code():
    for phrase in ("carpet cleaning", "rug cleaning", "shoe wash", "bag cleaning",
                   "wash and fold", "clean & press", "stitching"):
        res = sr.classify_service_request(phrase)
        assert res.is_supported, f"{phrase!r} should be supported, got {res.kind}"
        assert res.category_code, f"{phrase!r} should resolve to a category code"


def test_haircut_is_unsupported_not_a_catalogue_service():
    for phrase in ("haircut", "Do you provide haircuts?", "i want a hair cut",
                   "can i get a massage", "book me a taxi", "need a barber"):
        assert _kind(phrase) is K.UNSUPPORTED, phrase


def test_ambiguous_ironing_asks_for_clarification():
    assert _kind("ironing") is K.AMBIGUOUS
    assert _kind("I need ironing") is K.AMBIGUOUS


def test_bespoke_specialty_request_routes_to_bespoke_flow():
    res = sr.classify_service_request("Can you clean a heavily embroidered wedding dress?")
    assert res.kind is K.BESPOKE
    assert not res.is_supported  # bespoke is quoted, not booked as a standard service


def test_restoration_category_is_not_swept_up_as_bespoke():
    # "Restoration" is a real published category — must stay supported, not bespoke.
    assert sr.classify_service_request("restoration").is_supported


def test_unrecognised_text_is_none_not_unsupported():
    # Gibberish that is neither a catalogue match nor a clearly non-laundry term.
    assert _kind("asdfqwer zzz") is K.NONE


def test_unsupported_word_matching_is_whole_word_safe():
    # "cabinet" must not trip the "cab" unsupported term.
    assert _kind("clean my cabinet covers") is not K.UNSUPPORTED


def test_supported_categories_reads_the_live_catalogue():
    cats = sr.supported_categories()
    assert cats and all(isinstance(c, str) for c in cats)


def test_has_active_service_flag_does_not_change_classification():
    # Whether a booking exists or not, a haircut is still unsupported (the CALLER
    # decides to preserve the booking, not the classifier).
    assert _kind("haircut", has_active_service=True) is K.UNSUPPORTED
    assert _kind("haircut", has_active_service=False) is K.UNSUPPORTED
