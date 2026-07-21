"""WhatsApp provider config validation — mock | evolution | meta.

Each live provider requires ONLY its own vars; a blank var for the other
provider must never cause a failure. Pure-settings tests, no DB/network.
"""
import pytest

from settings import Settings

_EVO = dict(
    evolution_api_base_url="https://evo.example.com",
    evolution_api_key="evo-key",
    evolution_instance_name="lk-instance",
)
_META = dict(
    meta_whatsapp_access_token="tok",
    meta_whatsapp_phone_number_id="pnid",
    meta_whatsapp_business_account_id="waba",
    meta_whatsapp_verify_token="verify",
    meta_whatsapp_app_secret="secret",
)


def make(mode: str, **over) -> Settings:
    """Deterministic Settings (ignores .env and process env for provider vars)."""
    base = dict(whatsapp_mode=mode)
    base.update({k: "" for k in {**_EVO, **_META}})  # all provider vars blank
    base.update(over)
    return Settings(_env_file=None, **base)


# ------------------------------- mock --------------------------------------
def test_mock_requires_nothing():
    s = make("mock")
    s.validate_whatsapp_config()  # must not raise
    assert s.missing_whatsapp_config == []
    assert s.live_whatsapp_ready is False
    assert s.meta_live_ready is False


def test_mock_ignores_blank_provider_keys():
    # Blank Meta AND Evolution keys are fine in mock mode.
    make("mock").validate_whatsapp_config()


# ----------------------------- evolution -----------------------------------
def test_evolution_ready_with_its_vars():
    s = make("evolution", **_EVO)
    s.validate_whatsapp_config()
    assert s.live_whatsapp_ready is True
    assert s.meta_live_ready is False
    assert s.missing_whatsapp_config == []


def test_evolution_missing_raises_only_evolution_vars():
    s = make("evolution")
    assert s.missing_whatsapp_config == [
        "EVOLUTION_API_BASE_URL",
        "EVOLUTION_API_KEY",
        "EVOLUTION_INSTANCE_NAME",
    ]
    with pytest.raises(ValueError) as exc:
        s.validate_whatsapp_config()
    msg = str(exc.value)
    assert "EVOLUTION_API_BASE_URL" in msg
    assert "META_WHATSAPP" not in msg  # never complains about Meta in evolution mode


def test_evolution_does_not_require_meta_keys():
    # THE key requirement: blank Meta keys must not block evolution startup.
    s = make("evolution", **_EVO)  # Meta stays blank
    s.validate_whatsapp_config()  # must not raise
    assert s.live_whatsapp_ready is True


# ------------------------------- meta --------------------------------------
def test_meta_ready_with_its_vars():
    s = make("meta", **_META)
    s.validate_whatsapp_config()
    assert s.live_whatsapp_ready is True
    assert s.meta_live_ready is True


def test_meta_missing_raises_meta_vars():
    s = make("meta")
    with pytest.raises(ValueError) as exc:
        s.validate_whatsapp_config()
    msg = str(exc.value)
    assert "META_WHATSAPP_ACCESS_TOKEN" in msg
    assert "EVOLUTION_" not in msg  # never complains about Evolution in meta mode


def test_meta_does_not_require_evolution_keys():
    s = make("meta", **_META)  # Evolution stays blank
    s.validate_whatsapp_config()  # must not raise


# ---------------------------- unknown mode ---------------------------------
def test_unknown_mode_raises():
    with pytest.raises(ValueError) as exc:
        make("bogus").validate_whatsapp_config()
    assert "mock|evolution|meta" in str(exc.value)
