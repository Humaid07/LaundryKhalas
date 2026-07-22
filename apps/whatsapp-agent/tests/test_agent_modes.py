"""Agent operating modes + status model (safety-critical)."""
from services import order_store
from settings import Settings


def test_mode_defaults_to_paused_when_unset():
    # SAFE DEFAULT — the agent never auto-replies live by accident.
    assert Settings(_env_file=None).agent_operating_mode == "paused"
    assert Settings(_env_file=None).agent_replies_enabled is False


def test_mode_unknown_value_resolves_to_paused():
    s = Settings(_env_file=None, whatsapp_agent_mode="banana")
    assert s.agent_operating_mode == "paused"
    assert s.agent_replies_enabled is False


def test_mode_test_and_live_enable_replies():
    assert Settings(_env_file=None, whatsapp_agent_mode="test").agent_operating_mode == "test"
    assert Settings(_env_file=None, whatsapp_agent_mode="test").agent_replies_enabled is True
    assert Settings(_env_file=None, whatsapp_agent_mode="LIVE").agent_operating_mode == "live"
    assert Settings(_env_file=None, whatsapp_agent_mode="live").agent_replies_enabled is True


def test_paused_mode_disables_replies():
    assert Settings(_env_file=None, whatsapp_agent_mode="paused").agent_replies_enabled is False


def test_abandoned_is_a_valid_terminal_status():
    assert order_store.ABANDONED == "abandoned"
    assert order_store.ABANDONED in order_store.ORDER_STATUSES
    assert order_store.ABANDONED in order_store._TERMINAL          # not shown as active
    assert order_store.is_active_status(order_store.ABANDONED) is False
