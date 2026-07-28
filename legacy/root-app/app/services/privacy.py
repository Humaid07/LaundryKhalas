"""Privacy firewall.

Customer phone numbers, emails, and full addresses must never reach an LLM
prompt or a facility-facing output. This module is the single place that
performs that masking/redaction so every call site behaves consistently.
"""
import re

_PHONE_RE = re.compile(r"(\+?\d[\d\-\s]{6,}\d)")
_EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+\-]+@[a-zA-Z0-9\-]+\.[a-zA-Z0-9\-.]+")


def mask_phone(text: str) -> str:
    return _PHONE_RE.sub("[phone redacted]", text)


def mask_email(text: str) -> str:
    return _EMAIL_RE.sub("[email redacted]", text)


def mask_pii(text: str) -> str:
    """Mask phone numbers and emails in free text (e.g. before logging/LLM use)."""
    return mask_email(mask_phone(text))


def safe_address_for_llm(area: str | None, city: str | None, address_text: str | None = None) -> str:
    """Area/city only - never pass full street address text into an LLM prompt."""
    parts = [p for p in (area, city) if p]
    return ", ".join(parts) if parts else "address on file"


def customer_context_for_llm(
    *,
    name: str | None,
    area: str | None,
    city: str | None,
    preferred_language: str | None,
) -> dict:
    """Minimal customer context safe to include in an LLM prompt.

    Deliberately excludes phone, email, and full address - the agent only
    ever needs area/city to reason about pickup logistics.
    """
    return {
        "name": name or "customer",
        "area_city": safe_address_for_llm(area, city),
        "preferred_language": preferred_language or "en",
    }


def facility_facing_order_view(order: dict) -> dict:
    """Strip customer phone/email/full-address before any facility-facing output.

    `order` is expected to be a plain dict view of order + customer + address
    fields. Only area/city are kept for logistics; full address is included
    only if explicitly authorized by the caller via `include_full_address`.
    """
    include_full_address = order.get("include_full_address", False)
    view = {
        "order_id": order.get("order_id"),
        "service_type": order.get("service_type"),
        "items": order.get("items"),
        "area": order.get("area"),
        "city": order.get("city"),
        "pickup_window_start": order.get("pickup_window_start"),
        "pickup_window_end": order.get("pickup_window_end"),
    }
    if include_full_address:
        view["address_text"] = order.get("address_text")
    return view
