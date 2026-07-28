"""Outbound reply idempotency key (api/evolution_webhooks._reply_idem_key).

The key + the messages_repo.agent_reply_key_seen guard in _deliver ensure the
same logical reply for one turn is never sent twice (webhook redelivery, restart
re-drive, provider timeout/retry). This proves the pure key contract; the DB
lookup is a straight metadata->>'idem_key' existence check.
"""
from api.evolution_webhooks import _reply_idem_key
from services import booking_flow


def _reply(text, state="waiting_for_address"):
    return booking_flow.BookingReply(text=text, state=state)


def test_same_turn_and_reply_produce_the_same_key():
    r = _reply("What's the pickup address?")
    assert _reply_idem_key("turn_abc", r) == _reply_idem_key("turn_abc", r)


def test_different_turns_produce_different_keys():
    r = _reply("What's the pickup address?")
    assert _reply_idem_key("turn_abc", r) != _reply_idem_key("turn_def", r)


def test_different_reply_text_same_turn_differs():
    a = _reply_idem_key("turn_abc", _reply("What's the pickup address?"))
    b = _reply_idem_key("turn_abc", _reply("Which time window works best?"))
    assert a != b


def test_distinct_replies_in_one_turn_get_distinct_keys():
    # e.g. the confirmation message + the follow-up next-actions message: both in
    # the same turn but must both send (different body/state → different keys).
    confirm = _reply("Booking confirmed! Order LK-1.", state="post_order")
    actions = _reply("Anything else I can help with?", state="post_order")
    assert _reply_idem_key("turn_z", confirm) != _reply_idem_key("turn_z", actions)


def test_no_turn_id_yields_no_key():
    # Aggregation-off legacy path: wa_message_seen already dedupes, so content-only
    # keying (which could wrongly drop a legitimate repeat) is deliberately skipped.
    assert _reply_idem_key(None, _reply("hi")) is None
