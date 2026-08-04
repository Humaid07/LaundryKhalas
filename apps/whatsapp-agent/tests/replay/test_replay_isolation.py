"""Tests for synthetic-identity isolation (per-run namespace, no cross-run leak)."""
from __future__ import annotations

from replay_harness.core.models import Conversation
from replay_harness.runner import isolation


def _conv(chat_id, chash=None):
    return Conversation(
        source_archive="WhatsApp_All_Chats.zip",
        source_chat_id=chat_id,
        source_filename=f"{chat_id}.html",
        customer_identifier_hash=chash or ("h_" + chat_id),
    )


def test_isolated_chat_gives_unique_identity_per_chat():
    convs = [_conv("+974 1"), _conv("+974 2"), _conv("+974 3")]
    ids = isolation.assign_identities(convs, memory_mode="ISOLATED_CHAT", run_id="R1")
    phones = {i.phone for i in ids.values()}
    assert len(phones) == 3  # all distinct


def test_synthetic_phones_are_non_routable_999():
    convs = [_conv("+971 5"), _conv("+91 9")]
    ids = isolation.assign_identities(convs, run_id="R1")
    for ident in ids.values():
        assert ident.phone.startswith("+999")


def test_different_runs_use_different_namespace():
    convs = [_conv("+974 1")]
    a = isolation.assign_identities(convs, run_id="RUN_A")["+974 1"].phone
    b = isolation.assign_identities(convs, run_id="RUN_B")["+974 1"].phone
    # Different run ids -> different phone -> no cross-run state contamination.
    assert a != b


def test_same_run_is_deterministic():
    convs = [_conv("+974 1"), _conv("+974 2")]
    a = isolation.assign_identities(convs, run_id="RUN_X")
    b = isolation.assign_identities(convs, run_id="RUN_X")
    assert {k: v.phone for k, v in a.items()} == {k: v.phone for k, v in b.items()}


def test_customer_history_shares_identity_across_a_customers_chats():
    convs = [_conv("+974 1", "same"), _conv("+974 2", "same"), _conv("+974 3", "other")]
    ids = isolation.assign_identities(convs, memory_mode="CUSTOMER_HISTORY", run_id="R1")
    assert ids["+974 1"].phone == ids["+974 2"].phone
    assert ids["+974 1"].phone != ids["+974 3"].phone


def test_context_key_is_phone():
    convs = [_conv("+974 1")]
    ident = isolation.assign_identities(convs, run_id="R1")["+974 1"]
    assert ident.context_key == ident.phone
