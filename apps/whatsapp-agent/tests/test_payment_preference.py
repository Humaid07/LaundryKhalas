"""Stripe-first payment engine (services/payment_preference, spec §§13, 30)."""
from services import payment_preference as pp
from services.reply_style import normalize_customer_reply


def _run(messages, state=None):
    """Feed a sequence of customer messages through the engine, threading state."""
    state = state or pp.PaymentState()
    decisions = []
    for m in messages:
        d = pp.resolve_payment_turn(state, m)
        decisions.append(d)
        state = d.state
    return decisions, state


# --- the canonical three-step escalation (spec §30) --------------------------
def test_asks_about_cash_gets_stripe_regular():
    d = pp.resolve_payment_turn(pp.PaymentState(), "Do you accept cash?")
    assert d.template_id == "STRIPE_REGULAR_PAYMENT"
    assert d.text == pp.STRIPE_REGULAR_PAYMENT
    assert d.state.preference == pp.UNDECIDED
    assert d.state.stripe_preference_explained is True
    assert d.stop_pushing is False


def test_no_stripe_account_gets_no_account_required():
    d, state = _run(["Do you accept cash?", "I do not have Stripe."])
    assert d[1].template_id == "STRIPE_ACCOUNT_NOT_REQUIRED"
    assert d[1].text == pp.STRIPE_ACCOUNT_NOT_REQUIRED
    assert state.stripe_no_account_explained is True
    assert state.preference == pp.UNDECIDED


def test_still_prefers_cash_gets_cash_accepted_and_stops():
    d, state = _run(["Do you accept cash?", "I do not have Stripe.", "I still want cash please."])
    assert d[2].template_id == "CASH_ON_DELIVERY_ACCEPTED"
    assert state.preference == pp.CASH_ON_DELIVERY
    assert state.cash_accepted is True
    assert d[2].stop_pushing is True


def test_no_third_push_after_cash_accepted():
    # A 4th cash message after acceptance must NOT produce another explanation.
    d, state = _run(["cash?", "no stripe", "only cash", "cash on delivery yes"])
    assert state.preference == pp.CASH_ON_DELIVERY
    assert d[3].template_id is None          # nothing more to say
    assert d[3].stop_pushing is True


# --- shortcuts ---------------------------------------------------------------
def test_emphatic_cash_after_one_explanation_accepts_without_third_step():
    # "only cash" after the regular-method explanation is a clear refusal → accept.
    d, state = _run(["do you take cash", "only cash, I insist"])
    assert d[1].template_id == "CASH_ON_DELIVERY_ACCEPTED"
    assert state.preference == pp.CASH_ON_DELIVERY


def test_first_message_no_stripe_jumps_to_no_account_explanation():
    d = pp.resolve_payment_turn(pp.PaymentState(), "I don't have stripe, can I pay another way?")
    assert d.template_id == "STRIPE_ACCOUNT_NOT_REQUIRED"


def test_customer_chooses_stripe_locks_preference():
    d = pp.resolve_payment_turn(pp.PaymentState(), "Stripe is fine, send the link")
    assert d.state.preference == pp.STRIPE
    assert d.stop_pushing is True
    assert d.template_id == "STRIPE_CHOSEN_ACK"


def test_non_payment_message_is_not_handled():
    d = pp.resolve_payment_turn(pp.PaymentState(), "What time can you pick up?")
    assert d.handled is False
    assert d.template_id is None and d.text is None


def test_cash_link_not_created_flag_semantics():
    # The engine never creates a link; a cash order stays CASH_ON_DELIVERY until the
    # customer positively chooses Stripe later.
    _, state = _run(["cash on delivery please", "no stripe", "only cash"])
    assert state.preference == pp.CASH_ON_DELIVERY
    later = pp.resolve_payment_turn(state, "actually, stripe is fine, send the link")
    assert later.state.preference == pp.STRIPE


# --- persistence mapping (state <-> order row) ------------------------------
import datetime as _dt

_NOW = _dt.datetime(2026, 8, 5, 12, 0, tzinfo=_dt.timezone.utc)


def test_state_from_row_reads_columns_and_flags():
    row = {"payment_preference": pp.CASH_ON_DELIVERY,
           "stripe_preference_explained_at": _NOW,
           "stripe_no_account_explained_at": _NOW,
           "cash_requested_at": _NOW, "cash_accepted_at": _NOW}
    state = pp.state_from_row(row)
    assert state.preference == pp.CASH_ON_DELIVERY
    assert state.stripe_preference_explained and state.cash_accepted


def test_state_from_empty_row_is_fresh_undecided():
    state = pp.state_from_row(None)
    assert state.preference == pp.UNDECIDED
    assert not state.stripe_preference_explained and not state.cash_accepted


def test_updates_stamp_timestamp_only_on_first_transition():
    prev = {}  # nothing explained yet
    d = pp.resolve_payment_turn(pp.state_from_row(prev), "do you accept cash?")
    updates = pp.updates_for_state(prev, d.state, _NOW)
    assert updates["payment_preference"] == pp.UNDECIDED
    assert updates["stripe_preference_explained_at"] == _NOW
    # A later re-run must NOT overwrite the already-stamped moment.
    prev2 = {"stripe_preference_explained_at": _NOW, "payment_preference": pp.UNDECIDED}
    later = _dt.datetime(2026, 8, 5, 13, 0, tzinfo=_dt.timezone.utc)
    d2 = pp.resolve_payment_turn(pp.state_from_row(prev2), "do you accept cash?")
    updates2 = pp.updates_for_state(prev2, d2.state, later)
    assert "stripe_preference_explained_at" not in updates2  # unchanged


def test_row_roundtrip_through_escalation():
    row = {}
    for msg in ["do you take cash?", "I don't have stripe", "only cash please"]:
        d = pp.resolve_payment_turn(pp.state_from_row(row), msg)
        row = {**row, **pp.updates_for_state(row, d.state, _NOW)}
    assert row["payment_preference"] == pp.CASH_ON_DELIVERY
    assert row["cash_accepted_at"] == _NOW
    assert pp.state_from_row(row).cash_accepted is True


# --- follow-up arming gate (§14) --------------------------------------------
def test_wants_payment_followups_only_while_undecided():
    # First "do you accept cash?" → undecided, not stopping → arm follow-ups.
    d1 = pp.resolve_payment_turn(pp.PaymentState(), "do you accept cash?")
    assert pp.wants_payment_followups(d1) is True
    # Cash accepted (stop_pushing) → do NOT arm.
    d_cash = pp.resolve_payment_turn(
        pp.PaymentState(stripe_preference_explained=True, stripe_no_account_explained=True),
        "only cash please")
    assert d_cash.stop_pushing is True and pp.wants_payment_followups(d_cash) is False
    # Chose Stripe → do NOT arm.
    d_stripe = pp.resolve_payment_turn(pp.PaymentState(), "stripe is fine, send the link")
    assert pp.wants_payment_followups(d_stripe) is False
    # Non-payment message → do NOT arm.
    d_none = pp.resolve_payment_turn(pp.PaymentState(), "what time is pickup?")
    assert pp.wants_payment_followups(d_none) is False


# --- style safety ------------------------------------------------------------
def test_all_templates_pass_reply_style_validator():
    for text in pp.TEMPLATES.values():
        assert normalize_customer_reply(text).text == text  # no emoji/exclamation/dash changes
