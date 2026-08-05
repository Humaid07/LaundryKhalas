"""The single entry point for every payment call — mirrors llm/service.py.

No agent/booking/webhook code constructs a provider directly; they call
``get_gateway()``. A real Stripe provider is returned ONLY when the settings say
so (``stripe_live_ready``: mode test/live + key present). Otherwise the
deterministic ``MockStripeGateway`` is returned, guaranteeing mock-by-default.
"""
from __future__ import annotations

from services.payments.base import StripeGateway
from services.payments.mock_provider import MockStripeGateway
from settings import get_settings

_mock = MockStripeGateway()

# One reusable live provider per (key, mode, api_version) — rebuilt only when the
# resolved config changes (e.g. after a settings reload).
_provider_cache: dict[tuple, StripeGateway] = {}


def get_gateway() -> StripeGateway:
    settings = get_settings()
    if not settings.stripe_live_ready:
        return _mock

    cache_key = (
        settings.stripe_secret_key,
        settings.stripe_mode_normalized,
        settings.stripe_api_version,
        settings.stripe_default_currency,
    )
    cached = _provider_cache.get(cache_key)
    if cached is None:
        # Imported lazily so mock/offline runs never import the stripe SDK.
        from services.payments.stripe_provider import StripeProvider

        cached = StripeProvider(
            api_key=settings.stripe_secret_key,
            api_version=settings.stripe_api_version,
            default_currency=settings.stripe_default_currency,
            webhook_secret=settings.stripe_webhook_secret,
        )
        _provider_cache.clear()  # only the current config needs caching
        _provider_cache[cache_key] = cached
    return cached
