"""Pure message-aggregation logic (task spec §§14-23, tests 31-37/41-44/51-56).

No DB, no async, no network — the combine + flush-decision logic only.
"""
from datetime import datetime, timedelta

from services import message_aggregation as agg

T0 = datetime(2026, 7, 27, 18, 0, 0)


def _t(seconds):
    return T0 + timedelta(seconds=seconds)


# --- combine_fragments (spec §19) -------------------------------------------
def test_five_fragments_combine_in_order():
    frags = [{"text": t} for t in ["Hi", "I need wash and fold", "tomorrow",
                                    "after 6 PM", "from Dubai Marina"]]
    c = agg.combine_fragments(frags)
    assert c.message_count == 5
    assert c.text == "Hi\nI need wash and fold\ntomorrow\nafter 6 PM\nfrom Dubai Marina"
    assert c.fragments[0] == "Hi" and c.fragments[-1] == "from Dubai Marina"


def test_fragment_order_preserved_and_blank_skipped():
    frags = [{"text": "three shirts"}, {"text": "  "}, {"text": "two trousers"}]
    c = agg.combine_fragments(frags)
    assert c.text == "three shirts\ntwo trousers"     # order kept, blank dropped


def test_latest_interactive_selection_and_location_win():
    frags = [
        {"text": "wash and fold"},
        {"selection_id": "slot:morning_08_11"},
        {"text": "here is my location", "latitude": 25.07, "longitude": 55.13},
    ]
    c = agg.combine_fragments(frags)
    assert c.selection_id == "slot:morning_08_11"
    assert c.has_location is True and c.latitude == 25.07 and c.longitude == 55.13
    assert c.text == "wash and fold\nhere is my location"


def test_single_fragment_is_just_its_text():
    c = agg.combine_fragments([{"text": "How much is the 6 kg Wash & Fold bag?"}])
    assert c.text == "How much is the 6 kg Wash & Fold bag?"
    assert c.message_count == 1


# --- flush_decision: debounce + max window (spec §§15-16) --------------------
def test_not_ready_within_debounce_window():
    d = agg.flush_decision(T0, _t(2), _t(4), debounce_seconds=5, max_seconds=15)
    assert d.should_flush is False and d.reason == "not_ready"
    assert 2.9 < d.wait_seconds <= 3.0        # 5 - (4-2) = 3s until debounce


def test_flush_after_inactivity_debounce():
    # last fragment at t=2, now t=7.1 -> 5.1s idle >= 5s debounce -> flush
    d = agg.flush_decision(T0, _t(2), _t(7.1), debounce_seconds=5, max_seconds=15)
    assert d.should_flush is True and d.reason == "inactivity"


def test_debounce_resets_with_each_fragment():
    # A late fragment at t=10 pushes last_message_at forward; at t=12 still idle
    # only 2s -> NOT ready yet (the timer reset, spec §15).
    d = agg.flush_decision(T0, _t(10), _t(12), debounce_seconds=5, max_seconds=15)
    assert d.should_flush is False


def test_max_window_forces_flush_even_if_still_typing():
    # Fragments kept coming (last at t=14.5) but 15s since first -> hard cap flush.
    d = agg.flush_decision(T0, _t(14.5), _t(15.2), debounce_seconds=5, max_seconds=15)
    assert d.should_flush is True and d.reason == "max_window"


def test_explicit_send_closes_window_early():
    # Even 1s after the last fragment, an explicit "that's all" flushes now.
    d = agg.flush_decision(T0, _t(1), _t(2), debounce_seconds=5, max_seconds=15,
                           explicit_send=True)
    assert d.should_flush is True and d.reason == "explicit"


def test_interactive_selection_flushes_faster():
    d = agg.flush_decision(T0, _t(1), _t(2), debounce_seconds=5, max_seconds=15,
                           interactive_only=True)
    assert d.should_flush is True and d.reason == "interactive"


# --- is_explicit_send (spec §23) --------------------------------------------
def test_explicit_send_phrases_detected():
    for phrase in ["That's all.", "please confirm", "Done", "Confirm order",
                   "go ahead", "book it"]:
        assert agg.is_explicit_send(phrase) is True


def test_non_explicit_text_not_flagged():
    for phrase in ["I need wash and fold", "tomorrow", "from Dubai Marina", "3 shirts"]:
        assert agg.is_explicit_send(phrase) is False


# --- deadlines helper --------------------------------------------------------
def test_deadline_is_earlier_of_debounce_and_hard_cap():
    # first t0, last t=2: debounce deadline = t7, hard cap = t15 -> t7 wins.
    dl = agg.deadlines(T0, _t(2), debounce_seconds=5, max_seconds=15)
    assert dl == _t(7)
    # last fragment near the cap: hard cap wins.
    dl2 = agg.deadlines(T0, _t(14), debounce_seconds=5, max_seconds=15)
    assert dl2 == _t(15)
