"""Pricing lookups.

Prices always come from CountryConfig.pricing_config_json - this module
never invents or hardcodes a price. If a service type is not configured,
callers must treat that as "insufficient data" and escalate/ask, not guess.
"""


class PriceNotConfigured(Exception):
    """Raised when a requested service type has no price configured for the market."""


def get_retail_price(pricing_config: dict, service_type: str) -> dict:
    services = pricing_config.get("services", {})
    price = services.get(service_type)
    if price is None:
        raise PriceNotConfigured(f"No configured price for service_type={service_type!r}")
    return price


def calculate_order_total(pricing_config: dict, service_type: str, quantity: float = 1.0) -> float:
    price = get_retail_price(pricing_config, service_type)
    price_per_unit = float(price["price_per_unit"])
    min_price = float(price.get("min_price", 0))
    total = price_per_unit * max(quantity, 0)
    return round(max(total, min_price), 2)
