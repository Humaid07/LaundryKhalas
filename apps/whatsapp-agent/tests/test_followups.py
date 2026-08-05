"""Centralized follow-up scheduler policy (services/followups, spec §§14, 24, 25)."""
import datetime as _dt

import pytest

from services import clock
from services import followups as fu
from services.reply_style import normalize_customer_reply

_TZ = clock.zone_for_market("AE")


def _at(y, mo, d, h, mi=0):
    return _dt.datetime(y, mo, d, h, mi, tzinfo=_TZ)


@pytest.fixture(autouse=True)
def _fresh():
    fu.reload_config()
    yield
    fu.reload_config()


# --- config-driven timing ----------------------------------------------------
def test_offsets_and_priority_from_config():
    assert fu.offset_minutes(fu.PAYMENT_STRIPE) == 6
    assert fu.offset_minutes(fu.PAYMENT_CASH) == 15
    assert fu.offset_minutes(fu.WEB_ABANDONMENT_1) == 10
    assert fu.offset_minutes(fu.WEB_ABANDONMENT_2) == 40
    assert fu.offset_minutes(fu.WEB_ABANDONMENT_3) == 400  # 6h after fu2 (40 + 360)
    # payment outranks website abandonment (only-most-relevant, §25)
    assert fu.priority_rank(fu.PAYMENT_STRIPE) < fu.priority_rank(fu.WEB_ABANDONMENT_1)


def test_compute_due_at_adds_offset():
    anchor = _at(2026, 8, 5, 14, 0)
    assert fu.compute_due_at(anchor, fu.PAYMENT_STRIPE, market="AE") == _at(2026, 8, 5, 14, 6)


# --- 10 PM cutoff (spec §§14, 24) --------------------------------------------
def test_within_window():
    assert fu.within_messaging_window(_at(2026, 8, 5, 14, 0), market="AE") is True
    assert fu.within_messaging_window(_at(2026, 8, 5, 22, 0), market="AE") is False  # cutoff exclusive
    assert fu.within_messaging_window(_at(2026, 8, 5, 6, 0), market="AE") is False


def test_after_cutoff_moves_to_next_morning():
    # A payment follow-up due at 21:58 + 6 min = 22:04 → next day 08:00.
    due = fu.compute_due_at(_at(2026, 8, 5, 21, 58), fu.PAYMENT_STRIPE, market="AE")
    assert due == _at(2026, 8, 6, 8, 0)


def test_before_window_moves_to_same_day_start():
    assert fu.shift_into_window(_at(2026, 8, 5, 6, 30), market="AE") == _at(2026, 8, 5, 8, 0)


def test_within_window_unchanged():
    assert fu.shift_into_window(_at(2026, 8, 5, 15, 0), market="AE") == _at(2026, 8, 5, 15, 0)


# --- suppression -------------------------------------------------------------
@pytest.mark.parametrize("ctx_kwargs,reason", [
    ({"customer_replied": True}, "customer_replied"),
    ({"human_takeover": True}, "human_takeover"),
    ({"opted_out": True}, "opted_out"),
    ({"already_sent": True}, "already_sent"),
    ({"order_cancelled": True}, "order_cancelled"),
    ({"provider_blocked": True}, "provider_policy"),
])
def test_universal_suppressors(ctx_kwargs, reason):
    supp, why = fu.is_suppressed(fu.PAYMENT_STRIPE, fu.SuppressionContext(**ctx_kwargs))
    assert supp is True and why == reason


def test_payment_followup_suppressed_when_paid_or_cash_chosen():
    assert fu.is_suppressed(fu.PAYMENT_STRIPE, fu.SuppressionContext(paid=True))[0] is True
    assert fu.is_suppressed(fu.PAYMENT_STRIPE, fu.SuppressionContext(cash_selected=True))[0] is True


def test_web_abandonment_requires_consent_and_not_converted():
    assert fu.is_suppressed(fu.WEB_ABANDONMENT_1, fu.SuppressionContext(consent_absent=True))[0] is True
    assert fu.is_suppressed(fu.WEB_ABANDONMENT_1, fu.SuppressionContext(invalid_number=True))[0] is True
    assert fu.is_suppressed(fu.WEB_ABANDONMENT_2, fu.SuppressionContext(converted=True))[0] is True
    # a consented, un-converted lead is allowed
    assert fu.is_suppressed(fu.WEB_ABANDONMENT_1, fu.SuppressionContext())[0] is False


def test_quote_inactivity_suppressed_once_ordered():
    assert fu.is_suppressed(fu.QUOTE_INACTIVITY, fu.SuppressionContext(order_confirmed=True))[0] is True


# --- arbitration: only the most relevant (spec §25) --------------------------
def test_select_next_picks_highest_priority_due_and_unsuppressed():
    now = _at(2026, 8, 5, 15, 0)
    candidates = [
        fu.Candidate(fu.WEB_ABANDONMENT_1, _at(2026, 8, 5, 14, 50)),
        fu.Candidate(fu.PAYMENT_STRIPE, _at(2026, 8, 5, 14, 55)),  # higher priority
        fu.Candidate(fu.QUOTE_INACTIVITY, _at(2026, 8, 5, 16, 0)),  # not due yet
    ]
    chosen = fu.select_next(candidates, {}, now, market="AE")
    assert chosen.followup_type == fu.PAYMENT_STRIPE


def test_select_next_skips_suppressed_and_falls_through():
    now = _at(2026, 8, 5, 15, 0)
    candidates = [
        fu.Candidate(fu.PAYMENT_STRIPE, _at(2026, 8, 5, 14, 55)),
        fu.Candidate(fu.WEB_ABANDONMENT_1, _at(2026, 8, 5, 14, 50)),
    ]
    ctx = {fu.PAYMENT_STRIPE: fu.SuppressionContext(paid=True)}  # payment suppressed
    chosen = fu.select_next(candidates, ctx, now, market="AE")
    assert chosen.followup_type == fu.WEB_ABANDONMENT_1


def test_select_next_none_when_outside_window():
    # Everything due, but it is 23:00 local → nothing may be sent.
    now = _at(2026, 8, 5, 23, 0)
    candidates = [fu.Candidate(fu.PAYMENT_STRIPE, _at(2026, 8, 5, 22, 0))]
    assert fu.select_next(candidates, {}, now, market="AE") is None


def test_select_next_none_when_nothing_due():
    now = _at(2026, 8, 5, 15, 0)
    candidates = [fu.Candidate(fu.PAYMENT_STRIPE, _at(2026, 8, 5, 16, 0))]
    assert fu.select_next(candidates, {}, now, market="AE") is None


# --- idempotency + templates -------------------------------------------------
def test_dedupe_key_is_stable():
    assert fu.dedupe_key("c1", fu.PAYMENT_STRIPE) == fu.dedupe_key("c1", fu.PAYMENT_STRIPE)
    assert fu.dedupe_key("c1", fu.PAYMENT_STRIPE) != fu.dedupe_key("c1", fu.PAYMENT_CASH)


def test_render_fills_persona_and_passes_style_validator():
    msg = fu.render(fu.WEB_ABANDONMENT_1, persona="Zoya")
    assert msg.startswith("Hi, I am Zoya from Laundry Khalaas.")
    for ft in fu.FOLLOWUP_TEMPLATES:
        text = fu.render(ft, persona="Sara")
        assert normalize_customer_reply(text).text == text  # no emoji/exclamation/dash
