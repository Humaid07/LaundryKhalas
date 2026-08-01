"""Durable returning-customer memory shaping (spec 2026-08-01).

Turns DB-loaded, already-resolved customer data into a compact, structured block
that the agent receives as DYNAMIC context — placed AFTER the prompt-cache
breakpoint, never inside the shared 1h-cached system prompt (see
``agents/whatsapp_agent/context_assembly.py``). Prompt caching is a cost/latency
optimisation, NOT customer memory; memory is reloaded from the database at the
start of every conversation and passed through here.

This module is PURE (no DB, no I/O): the caller resolves the customer by
normalized WhatsApp number, loads the confirmed profile / saved address / pin /
persona, and passes them in. That keeps memory strictly per-customer, so one
customer's details can never leak into another conversation — an empty or
mismatched customer yields ``{}``.

Privacy firewall (CLAUDE.md §7): the phone number is surfaced MASKED; the full
``phone_e164`` stays backend-only and never enters model context.
"""
from __future__ import annotations

from typing import Any

# Name sources the backend trusts enough to greet a returning customer by name.
_TRUSTED_NAME_SOURCES = {"CUSTOMER_PROVIDED", "CUSTOMER_CONFIRMED", "CONFIRMED"}


def _num(v: Any) -> float | None:
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


def _confirmed_name(customer: dict, confirmed_name: str | None) -> tuple[str | None, str | None]:
    """Return (name, source) for a name safe to greet with, else (None, None).
    An explicit confirmed_name (from the confirmed-name repo lookup) wins; then a
    customer_name with a trusted source. An unconfirmed WhatsApp profile name is
    NOT used for greeting."""
    if confirmed_name and str(confirmed_name).strip():
        return str(confirmed_name).strip(), "CUSTOMER_CONFIRMED"
    src = (customer.get("customer_name_source") or "").upper()
    name = customer.get("customer_name")
    if name and str(name).strip() and src in _TRUSTED_NAME_SOURCES:
        return str(name).strip(), src
    return None, None


def shape_saved_address(addr: dict | None) -> dict | None:
    """Shape a saved-address record into the memory block's ``saved_address``.
    ``pin_available`` is true only when BOTH coordinates are present and finite —
    never inferred from typed text. Returns None when there is nothing usable."""
    if not addr:
        return None
    lat, lng = _num(addr.get("latitude")), _num(addr.get("longitude"))
    typed = addr.get("typed_address") or addr.get("pickup_address") or addr.get("address")
    if not typed and lat is None and lng is None:
        return None
    return {
        "address_id": str(addr["address_id"]) if addr.get("address_id") else None,
        "typed_address": typed or None,
        "building": addr.get("building") or addr.get("building_name"),
        "floor": addr.get("floor"),
        "unit": addr.get("unit") or addr.get("apartment_number") or addr.get("villa_number"),
        "area": addr.get("area") or addr.get("pickup_area"),
        "city": addr.get("city"),
        "emirate": addr.get("emirate") or addr.get("pickup_emirate"),
        "latitude": lat,
        "longitude": lng,
        "pin_available": lat is not None and lng is not None,
    }


def build_returning_customer_context(
    customer: dict | None,
    *,
    confirmed_name: str | None = None,
    persona: str | None = None,
    saved_address: dict | None = None,
    last_completed_order_id: Any = None,
) -> dict:
    """Build the structured returning-customer memory block for the agent's
    dynamic context. Pure and per-customer: returns ``{}`` for an unusable
    customer so nothing is ever fabricated or leaked across conversations.

    Only includes memory that is genuinely known for THIS customer. The number is
    masked; a name is included only when it is trusted (confirmed/provided), so
    the agent never greets with a stale or unconfirmed name."""
    if not customer or not customer.get("id"):
        return {}

    ctx: dict[str, Any] = {
        "returning_customer": True,
        "customer_id": str(customer["id"]),
        "whatsapp_number": customer.get("masked_phone") or None,
    }
    name, source = _confirmed_name(customer, confirmed_name)
    if name:
        ctx["customer_name"] = name
        ctx["customer_name_source"] = source
    if persona:
        ctx["assigned_persona"] = persona
    shaped = shape_saved_address(saved_address)
    if shaped:
        ctx["saved_address"] = shaped
    if last_completed_order_id:
        ctx["last_completed_order_id"] = str(last_completed_order_id)

    # A customer row exists, but if there is nothing durable to remember (no
    # trusted name, no saved address, no prior order) the customer is effectively
    # new for memory purposes — return {} so the agent gives a normal greeting
    # rather than a hollow "welcome back".
    if not any(k in ctx for k in ("customer_name", "saved_address", "last_completed_order_id")):
        return {}
    return ctx
