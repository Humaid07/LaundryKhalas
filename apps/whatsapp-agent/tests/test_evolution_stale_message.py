"""Guard against replying to history-sync backlog (unsolicited sends).

On an Evolution/Baileys socket reconnect, WhatsApp re-delivers old messages via
messages.upsert. Each carries its ORIGINAL (old) send time, so the webhook drops
anything older than the freshness window instead of treating it as a live turn.
"""
from __future__ import annotations

import datetime as _dt

from api.evolution_webhooks import _is_stale_inbound, _turn_is_stale
from channels.evolution_whatsapp import _parse_message_timestamp, parse_evolution_webhook


def _dt_ago(seconds: int, *, now: _dt.datetime) -> _dt.datetime:
    return now - _dt.timedelta(seconds=seconds)


# --- timestamp parsing ------------------------------------------------------
def test_parse_message_timestamp_forms():
    assert _parse_message_timestamp(1000) == 1000
    assert _parse_message_timestamp("1699999999") == 1699999999
    assert _parse_message_timestamp({"low": 1234, "high": 0}) == 1234
    assert _parse_message_timestamp(None) is None
    assert _parse_message_timestamp("not-a-number") is None
    assert _parse_message_timestamp(True) is None  # bool is not a timestamp


def test_parser_includes_message_timestamp():
    payload = {
        "event": "messages.upsert",
        "data": {
            "key": {"remoteJid": "919322287956@s.whatsapp.net", "fromMe": False, "id": "M1"},
            "message": {"conversation": "How much for wash and fold?"},
            "messageTimestamp": 1735000000,
            "pushName": "Test",
        },
    }
    out = parse_evolution_webhook(payload)
    assert len(out) == 1
    assert out[0]["message_timestamp"] == 1735000000
    assert out[0]["text"] == "How much for wash and fold?"


# --- staleness guard --------------------------------------------------------
NOW = 1_000_000.0


def test_recent_message_is_not_stale():
    assert _is_stale_inbound(int(NOW - 5), 120, now_epoch=NOW) is False


def test_old_backlog_message_is_stale():
    assert _is_stale_inbound(int(NOW - 3600), 120, now_epoch=NOW) is True  # 1h old → history sync


def test_missing_timestamp_fails_open():
    # can't tell → treat as live (never drop a real message on a parse quirk)
    assert _is_stale_inbound(None, 120, now_epoch=NOW) is False


def test_disabled_guard_never_stale():
    assert _is_stale_inbound(int(NOW - 999999), 0, now_epoch=NOW) is False


def test_clock_skew_tolerated():
    # a message timestamped slightly in the future (drift) is not stale
    assert _is_stale_inbound(int(NOW + 30), 120, now_epoch=NOW) is False


def test_boundary_just_within_window():
    assert _is_stale_inbound(int(NOW - 120), 120, now_epoch=NOW) is False   # exactly at window
    assert _is_stale_inbound(int(NOW - 121), 120, now_epoch=NOW) is True    # just past


# --- recovery-path guard (buffered turns re-driven on restart) --------------
def test_recovery_skips_stale_turn():
    now = _dt.datetime(2026, 8, 6, 1, 0, 0, tzinfo=_dt.timezone.utc)
    stale = {"turn_id": "t1", "last_message_at": _dt_ago(3600, now=now)}  # 1h old
    assert _turn_is_stale(stale, 120, now=now) is True


def test_recovery_keeps_fresh_pending_turn():
    now = _dt.datetime(2026, 8, 6, 1, 0, 0, tzinfo=_dt.timezone.utc)
    fresh = {"turn_id": "t2", "last_message_at": _dt_ago(10, now=now)}  # 10s old → real pending
    assert _turn_is_stale(fresh, 120, now=now) is False


def test_recovery_guard_fails_open():
    now = _dt.datetime(2026, 8, 6, 1, 0, 0, tzinfo=_dt.timezone.utc)
    assert _turn_is_stale(None, 120, now=now) is False              # no turn
    assert _turn_is_stale({"turn_id": "t"}, 120, now=now) is False  # no timestamp
    assert _turn_is_stale({"last_message_at": _dt_ago(9999, now=now)}, 0, now=now) is False  # disabled
