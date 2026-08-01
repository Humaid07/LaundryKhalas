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


def test_wedding_dress_routes_to_specialist():
    # Spec §2.8: wedding dresses are handled by a specialist (route-to-human),
    # NOT quoted — routing wins over both the bespoke photo-flow and Clean & Press.
    res = sr.classify_service_request("Can you clean a heavily embroidered wedding dress?")
    assert res.kind is K.ROUTE
    assert res.routing_category == "WEDDING_DRESS"
    assert not res.is_supported  # routed, not booked/quoted as a standard service


def test_bespoke_specialty_marker_still_routes_to_bespoke_flow():
    # A specialty marker with no route-to-human category → the bespoke photo-quote flow.
    res = sr.classify_service_request("beaded custom-made gown")
    assert res.kind is K.BESPOKE
    assert not res.is_supported


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


# --- repair / alteration classification (spec 2026-08-01 §2) -----------------
def test_standard_alteration_words_resolve_to_alterations():
    # Hemming / shortening / waist adjustment etc. are routine alterations — a
    # supported catalogue service, never a rejected "repair".
    for phrase in ("shorten these jeans", "take in the waist", "loosen my kurta",
                   "tighten my dress", "lengthen my abaya"):
        res = sr.classify_service_request(phrase)
        assert res.is_supported, f"{phrase!r} should be a supported alteration, got {res.kind}"
        assert res.category_code == "ALTERATIONS"


def test_garment_repair_routes_to_alterations_not_rejected():
    # A garment repair phrased with "repair"/"fix"/"mend" + a clothing item is a
    # real service (routes to Alterations), NOT a decline.
    for phrase in ("can you repair the zip on my jeans", "fix the button on my shirt",
                   "mend a tear in my dress", "repair the seam on my jacket"):
        res = sr.classify_service_request(phrase)
        assert res.kind is K.ALIAS and res.category_code == "ALTERATIONS", phrase
        assert res.reason == "garment_repair"


def test_leather_shoe_repair_routes_to_restoration_photo_flow():
    for phrase in ("repair my leather shoes", "fix the sole of my boots",
                   "mend my handbag strap"):
        assert _kind(phrase) is K.BESPOKE, phrase


def test_non_laundry_repair_is_the_only_repair_declined():
    for phrase in ("repair my phone screen", "fix my car engine", "repair my laptop",
                   "can you fix my washing machine", "mend the broken cabinet door"):
        assert _kind(phrase) is K.UNSUPPORTED, phrase


def test_bare_repair_request_asks_one_clarification():
    res = sr.classify_service_request("can you repair this?")
    assert res.kind is K.AMBIGUOUS and res.reason == "ambiguous_repair"
    res2 = sr.classify_service_request("I need something fixed")
    assert res2.kind is K.AMBIGUOUS and res2.reason == "ambiguous_repair"


def test_repair_object_word_boundary_is_garment_safe():
    # "cardigan"/"scarf" must NOT trip the non-laundry "car" object → they are
    # garments, so a repair on them routes to Alterations, never declined.
    assert sr.classify_service_request("repair my cardigan").category_code == "ALTERATIONS"
    assert _kind("fix the hem of my scarf") is not K.UNSUPPORTED
