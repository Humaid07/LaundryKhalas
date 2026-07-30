"""Centralized facility-handoff serializer.

ONE place that decides what customer/order data a facility may see. Customer-data
sharing is gated by config (FACILITY_SHARE_*), so it can be switched off later
(e.g. once the driver app exists) WITHOUT breaking routing or historical records.

Never exposed to a facility: internal margins, customer tier, competing facility
quotations, internal rankings, routing calculations, payment credentials, or the
full conversation history.

Pure function over dicts — unit-testable; the asyncpg wiring lives in
services/facility_routing.py + db/repositories/facility_orders_repo.py.
"""

from __future__ import annotations

from dataclasses import dataclass

from services import order_notes as notes_mod

# Note categories surfaced to the facility, grouped into operational sections.
_FACILITY_NOTE_SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("pickup_instructions", ("PICKUP_INSTRUCTION",)),
    ("delivery_instructions", ("DELIVERY_INSTRUCTION",)),
    ("access_instructions", ("ACCESS_INSTRUCTION",)),
    ("contact_preferences", ("CONTACT_PREFERENCE",)),
    ("timing_preferences", ("TIMING_PREFERENCE",)),
    ("item_handling", ("ITEM_HANDLING",)),
    ("stains_and_damage", ("STAIN_NOTE", "EXISTING_DAMAGE")),
    ("special_care", ("SPECIAL_CARE",)),
    ("facility_instructions", ("FACILITY_INSTRUCTION",)),
    ("inspection_requirements", ("INSPECTION_REQUIREMENT",)),
    ("other_notes", ("OTHER_OPERATIONAL_NOTE",)),
)


@dataclass(frozen=True)
class FacilityShareConfig:
    """Which direct customer-contact fields may be shared with a facility."""
    customer_name: bool = True
    customer_phone: bool = True
    typed_address: bool = True
    location_pin: bool = True


def _grouped_notes(active_notes: list[dict]) -> dict[str, list[str]]:
    by_cat = notes_mod.group_active_by_category(active_notes)
    out: dict[str, list[str]] = {}
    for section, cats in _FACILITY_NOTE_SECTIONS:
        texts: list[str] = []
        for c in cats:
            texts.extend(by_cat.get(c, []))
        if texts:
            out[section] = texts
    return out


def _typed_address(order: dict) -> dict:
    parts = {
        k: order.get(k)
        for k in (
            "pickup_address", "building_name", "villa_number", "apartment_number",
            "floor", "room_number", "landmark", "access_details",
            "pickup_area", "area", "city", "pickup_emirate",
        )
        if order.get(k)
    }
    return parts


def build_facility_handoff_payload(
    *,
    order: dict,
    active_notes: list[dict] | None,
    customer: dict | None,
    share: FacilityShareConfig,
    item_images: list[dict] | None = None,
) -> dict:
    """Build the sanitized facility-facing payload for one confirmed order.

    Only whitelisted fields are emitted; there is no path for margins/tier/
    rankings/rates/payment to leak because they are never read here.
    """
    active_notes = active_notes or []
    payload: dict = {
        "order_id": order.get("order_id"),
        "service": order.get("service_display_name") or order.get("service_name_snapshot") or order.get("service"),
        "service_id": order.get("service_id"),
        "items": _items(order),
        "pickup_date": _iso(order.get("pickup_date")),
        "pickup_window": _pickup_window(order),
        "notes": _grouped_notes(active_notes),
    }

    # Location pin — the primary routing input (config-gated).
    if share.location_pin and order.get("pickup_latitude") is not None and order.get("pickup_longitude") is not None:
        payload["location_pin"] = {
            "latitude": order.get("pickup_latitude"),
            "longitude": order.get("pickup_longitude"),
            "type": order.get("location_type"),
            "name": order.get("location_name"),
        }
    payload["location_pin_status"] = order.get("location_pin_status") or ("received" if order.get("pickup_latitude") is not None else "missing")

    # Typed address — human navigation (config-gated).
    if share.typed_address:
        addr = _typed_address(order)
        if addr:
            payload["pickup_address"] = addr
    else:
        # Routing must still work: keep coarse area/city only.
        payload["pickup_area"] = order.get("pickup_area") or order.get("area")
        payload["city"] = order.get("city")

    # Customer contact (config-gated).
    if customer:
        if share.customer_name and (order.get("customer_name") or customer.get("customer_name") or customer.get("display_name")):
            payload["customer_name"] = order.get("customer_name") or customer.get("customer_name") or customer.get("display_name")
        if share.customer_phone and (customer.get("normalized_contact_number") or customer.get("phone_e164")):
            payload["customer_whatsapp_number"] = customer.get("normalized_contact_number") or customer.get("phone_e164")

    if item_images:
        payload["item_images"] = [
            {"id": im.get("id"), "url": im.get("url"), "stage": im.get("stage")}
            for im in item_images
            if im.get("approved", True)
        ]

    return payload


def _items(order: dict) -> list[dict]:
    raw = order.get("line_items") or order.get("items") or []
    out: list[dict] = []
    if isinstance(raw, list):
        for it in raw:
            if isinstance(it, dict):
                out.append({
                    "name": it.get("name") or it.get("item") or it.get("label"),
                    "quantity": it.get("quantity") or it.get("qty"),
                    "measure": it.get("measure") or it.get("unit"),
                })
    return out


def _pickup_window(order: dict) -> str | None:
    return order.get("pickup_slot_label") or order.get("pickup_slot") or None


def _iso(v) -> str | None:
    if v is None:
        return None
    try:
        return v.isoformat()
    except AttributeError:
        return str(v)


def config_from_settings(settings) -> FacilityShareConfig:
    """Read the FACILITY_SHARE_* flags off the pydantic Settings object."""
    return FacilityShareConfig(
        customer_name=bool(getattr(settings, "facility_share_customer_name", True)),
        customer_phone=bool(getattr(settings, "facility_share_customer_phone", True)),
        typed_address=bool(getattr(settings, "facility_share_typed_address", True)),
        location_pin=bool(getattr(settings, "facility_share_location_pin", True)),
    )
