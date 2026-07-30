"""WhatsApp location-pin capture + typed-address gap detection (pure).

The location pin (lat/long) and the typed address serve different purposes:
  * pin  -> distance / nearest-facility routing / service-radius / driver routing
  * typed address -> human-readable pickup (building, apartment, floor, room…)

This module parses a real Evolution location event into structured fields and
never invents coordinates. It also computes what address detail is still missing
and the pin status shown in the summary.
"""

from __future__ import annotations

from dataclasses import dataclass

# received: a valid pin is on file; missing: none yet; manual_review: customer
# genuinely cannot share one -> Operations routes it (no invented coordinates).
PIN_RECEIVED = "received"
PIN_MISSING = "missing"
PIN_MANUAL_REVIEW = "manual_review"

# The typed-address parts we consider "unit detail" for a residential pickup.
_UNIT_FIELDS = ("building_name", "villa_number", "apartment_number", "floor", "room_number")


@dataclass(frozen=True)
class LocationCapture:
    ok: bool
    latitude: float | None = None
    longitude: float | None = None
    location_name: str | None = None
    provider_address: str | None = None
    location_type: str | None = None  # static | live
    accuracy: float | None = None
    reason: str = ""


def _num(v) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f


def process_whatsapp_location(event: dict | None) -> LocationCapture:
    """Parse an Evolution location message into validated coordinates.

    ``event`` is the ``locationMessage`` / ``liveLocationMessage`` object (or a
    flattened ``{latitude, longitude, ...}`` dict). Returns ``ok=False`` when the
    coordinates are absent or out of range — coordinates are NEVER fabricated.
    """
    if not isinstance(event, dict) or not event:
        return LocationCapture(False, reason="empty")

    live = isinstance(event.get("liveLocationMessage"), dict)
    inner = event.get("liveLocationMessage") or event.get("locationMessage") or event
    lat = _num(inner.get("degreesLatitude", inner.get("latitude")))
    lng = _num(inner.get("degreesLongitude", inner.get("longitude")))
    if lat is None or lng is None:
        return LocationCapture(False, reason="no_coordinates")
    if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lng <= 180.0):
        return LocationCapture(False, reason="out_of_range")

    return LocationCapture(
        ok=True,
        latitude=lat,
        longitude=lng,
        location_name=(inner.get("name") or None),
        provider_address=(inner.get("address") or None),
        location_type="live" if live else "static",
        accuracy=_num(inner.get("accuracyInMeters")),
    )


def has_pin(order: dict) -> bool:
    return order.get("pickup_latitude") is not None and order.get("pickup_longitude") is not None


def pin_status(order: dict) -> str:
    if has_pin(order):
        return PIN_RECEIVED
    existing = str(order.get("location_pin_status") or "").strip().lower()
    if existing == PIN_MANUAL_REVIEW:
        return PIN_MANUAL_REVIEW
    return PIN_MISSING


def has_typed_address(order: dict) -> bool:
    if str(order.get("pickup_address") or "").strip():
        return True
    return any(str(order.get(f) or "").strip() for f in _UNIT_FIELDS)


def missing_address_fields(order: dict) -> list[str]:
    """Unit-detail fields still absent. Empty when a pickup_address free-text or any
    unit field is present (we don't nag for every part)."""
    if has_typed_address(order):
        return []
    return list(_UNIT_FIELDS)


def routing_ready(order: dict) -> bool:
    """Distance-based routing is only valid when a real pin exists."""
    return has_pin(order)
