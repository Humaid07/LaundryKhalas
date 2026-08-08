"""Phase 3: deterministic price-signal detection (spec §17) so discount-follow-up
scheduling is testable without the live shadow classifier."""
from services.hesitation import is_price_enquiry, is_price_objection


def test_price_enquiry_is_not_objection():
    for t in ["How much for 5 shirts?", "What's the price for a suit?",
              "How much?", "what is the cost of dry cleaning"]:
        assert is_price_enquiry(t), t
        assert not is_price_objection(t), t


def test_real_price_objection():
    for t in ["That's too expensive.", "that is way too much",
              "a bit pricey", "can you make it cheaper", "that's a lot"]:
        assert is_price_objection(t), t


def test_objection_wins_when_both_signals_present():
    # "how much cheaper can you go" reads as an objection/negotiation, not a plain enquiry
    assert is_price_objection("how much cheaper can you go")


def test_neutral_text_is_neither():
    assert not is_price_enquiry("I need a pickup from Marina tomorrow")
    assert not is_price_objection("I need a pickup from Marina tomorrow")
