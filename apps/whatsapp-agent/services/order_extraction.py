"""Extraction / order-state layer for the WhatsApp order-capture flow.

Pulls STRUCTURED customer + order details out of free-text WhatsApp messages so
the backend can persist them (customer row, order draft, order events) instead of
only storing the raw transcript. Deterministic — no LLM call.

Service/area/time slot extraction is delegated to the SAME helpers the agent
already uses (``agents.whatsapp_agent.tools``) so the service catalogue and area
gazetteer live in exactly one place. On top of those this module adds
name / address / items-with-quantity / payment-method / confirmation detection.

``extract_customer_order_details(text, context)`` MERGES the current message onto
any previously-accumulated ``OrderDetails`` (later turn wins for scalar fields;
items accumulate). ``accumulate_from_messages`` folds a whole customer-message
history into one ``OrderDetails`` — that is what gives the conversation memory
across turns (a name in message 2 and an address in message 4 attach to the same
draft). No raw phone/address is logged here; callers store address backend-only.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from agents.whatsapp_agent import tools
from rules import service_by_id, service_labels

# --------------------------------------------------------------------------
# Area -> city map (built from the same config the agent's gazetteer uses)
# --------------------------------------------------------------------------
def _build_area_city_map() -> tuple[dict[str, str], dict[str, str]]:
    """Returns (area_lower -> city, city_lower -> city_display) from the KB's
    ``service_areas`` section (city keys -> area lists)."""
    from agents.whatsapp_agent.prompts import load_knowledge

    kb = load_knowledge()
    areas_cfg = kb.get("service_areas", {})
    area_to_city: dict[str, str] = {}
    cities: dict[str, str] = {}
    for city, value in areas_cfg.items():
        if city in ("note", "aliases") or not isinstance(value, list):
            continue
        cities[city.lower()] = city
        for area in value:
            area_to_city[area.lower()] = city
    return area_to_city, cities


_AREA_TO_CITY, _CITY_DISPLAY = _build_area_city_map()


def area_to_city(area: str | None) -> str | None:
    if not area:
        return None
    return _AREA_TO_CITY.get(area.lower())


def _detect_city(text: str) -> str | None:
    lowered = text.lower()
    for city_lower, display in _CITY_DISPLAY.items():
        if re.search(r"\b" + re.escape(city_lower) + r"\b", lowered):
            return display
    return None


# --------------------------------------------------------------------------
# Name
# --------------------------------------------------------------------------
# Only STRONG, unambiguous triggers — bare "I am" / "I'm" are deliberately
# excluded ("I'm in Dubai", "I am looking for..." are not names).
_NAME_TRIGGERS = re.compile(
    r"\b(?:my name is|name is|name'?s|this is|call me|i am called|i'?m called)\s+"
    r"([A-Za-z][A-Za-z'\- ]{1,40})",
    re.IGNORECASE,
)
# Words that end a captured name (a name never runs into these).
_NAME_STOPWORDS = {
    "and", "i", "im", "from", "in", "at", "here", "live", "living", "staying",
    "need", "want", "the", "is", "calling", "speaking", "my", "pickup", "please",
    "for", "with", "we", "our", "a", "an",
}


def extract_name(text: str) -> str | None:
    match = _NAME_TRIGGERS.search(text or "")
    if not match:
        return None
    words = re.findall(r"[A-Za-z'\-]+", match.group(1))
    kept: list[str] = []
    for w in words:
        if w.lower() in _NAME_STOPWORDS:
            break
        kept.append(w)
        if len(kept) >= 3:  # a name is at most a few tokens
            break
    if not kept:
        return None
    return " ".join(part.capitalize() for part in kept)


# --------------------------------------------------------------------------
# Address
# --------------------------------------------------------------------------
_ADDRESS_TRIGGERS = re.compile(
    r"\b(?:pickup address is|pickup address|pick ?up is|pickup is|address is|"
    r"my address is|address:?|pick ?up from|pickup from|collect from|located at|"
    r"i am at|i'?m at)\s*[:\-]?\s*(.+)$",
    re.IGNORECASE,
)
# If no trigger fires but the message clearly describes a location, treat it as
# an address (building / tower / street / apartment style keywords).
_ADDRESS_KEYWORDS = re.compile(
    r"\b(tower|building|villa|flat|apartment|apt|street|st\.?|road|rd\.?|block|"
    r"gate|residence|floor|room|near|behind|opposite)\b",
    re.IGNORECASE,
)


def extract_address(text: str, *, area: str | None = None) -> str | None:
    text = (text or "").strip()
    candidate: str | None = None

    match = _ADDRESS_TRIGGERS.search(text)
    if match:
        candidate = match.group(1).strip()
    elif _ADDRESS_KEYWORDS.search(text) and len(text.split()) <= 20:
        # No explicit trigger, but the message looks like an address line.
        candidate = text

    if not candidate:
        return None

    candidate = candidate.strip(" ,.-")
    # Drop a leading area/city we already captured separately, so the stored
    # address is the specific line ("Marina Gate, Tower 1"), not a duplicate of
    # the area. Best-effort only.
    for prefix in (area, area_to_city(area)):
        if prefix and candidate.lower().startswith(prefix.lower()):
            candidate = candidate[len(prefix):].strip(" ,.-")
    return candidate or None


# --------------------------------------------------------------------------
# Items (quantity + laundry noun)
# --------------------------------------------------------------------------
_NUM_WORDS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "couple": 2,
    "few": 3, "pair": 2,
}
# Canonical singular laundry items we recognise (plural handled by stripping 's').
_ITEM_NOUNS = {
    "suit": "Suit", "shirt": "Shirt", "trouser": "Trousers", "pant": "Trousers",
    "dress": "Dress", "jacket": "Jacket", "coat": "Coat", "blazer": "Blazer",
    "blanket": "Blanket", "duvet": "Duvet", "comforter": "Comforter",
    "curtain": "Curtain", "sofa": "Sofa", "couch": "Sofa", "carpet": "Carpet",
    "rug": "Rug", "kandura": "Kandura", "abaya": "Abaya", "thobe": "Thobe",
    "kurta": "Kurta", "saree": "Saree", "bedsheet": "Bedsheet", "sheet": "Bedsheet",
    "towel": "Towel", "jean": "Jeans", "sweater": "Sweater", "scarf": "Scarf",
    "tie": "Tie", "uniform": "Uniform", "cushion": "Cushion", "pillow": "Pillow",
    "tshirt": "T-Shirt", "kaftan": "Kaftan",
}
_ITEM_PATTERN = re.compile(
    r"\b(\d{1,3}|a|an|one|two|three|four|five|six|seven|eight|nine|ten|couple|few|pair)"
    r"\s+(?:of\s+)?([a-z][a-z\-]+?)s?\b",
    re.IGNORECASE,
)


def extract_items(text: str) -> list[dict]:
    """Returns ``[{"item": "Suit", "quantity": 2}, ...]`` for recognised laundry
    nouns with a leading count. Unknown nouns are ignored (no invented items)."""
    found: dict[str, int] = {}
    for qty_raw, noun_raw in _ITEM_PATTERN.findall(text or ""):
        noun = noun_raw.lower().rstrip("s") if noun_raw.lower() not in _ITEM_NOUNS else noun_raw.lower()
        canonical = _ITEM_NOUNS.get(noun) or _ITEM_NOUNS.get(noun_raw.lower())
        if not canonical:
            continue
        if qty_raw.isdigit():
            qty = int(qty_raw)
        else:
            qty = _NUM_WORDS.get(qty_raw.lower(), 1)
        found[canonical] = max(found.get(canonical, 0), qty)
    return [{"item": name, "quantity": qty} for name, qty in found.items()]


# --------------------------------------------------------------------------
# Payment method
# --------------------------------------------------------------------------
_PAYMENT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(cash on delivery|cash|cod|pay on delivery|pay cash)\b", re.I), "Cash on delivery"),
    (re.compile(r"\b(apple pay)\b", re.I), "Apple Pay"),
    (re.compile(r"\b(google pay|g pay|gpay)\b", re.I), "Google Pay"),
    (re.compile(r"\b(credit card|debit card|card|visa|master\s?card)\b", re.I), "Card"),
    (re.compile(r"\b(bank transfer|online payment|online|transfer|link)\b", re.I), "Online payment"),
]


def extract_payment_method(text: str) -> str | None:
    for pattern, label in _PAYMENT_PATTERNS:
        if pattern.search(text or ""):
            return label
    return None


# --------------------------------------------------------------------------
# Delivery slot / confirmation / language
# --------------------------------------------------------------------------
_DELIVERY_TRIGGER = re.compile(
    r"\b(?:deliver(?:y)?|drop ?off|return|bring back)\b.*?"
    r"\b(today|tomorrow|tonight|morning|afternoon|evening|this week|next week|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday|\d{1,2}\s?(?:am|pm))\b",
    re.IGNORECASE,
)
_CONFIRM_PATTERN = re.compile(
    r"\b(confirm|confirmed|book it|go ahead|place the order|that'?s correct|proceed)\b",
    re.IGNORECASE,
)
_ARABIC = re.compile(r"[؀-ۿ]")


def extract_delivery_slot(text: str) -> str | None:
    m = _DELIVERY_TRIGGER.search(text or "")
    return m.group(1).lower() if m else None


def is_confirmation(text: str) -> bool:
    return bool(_CONFIRM_PATTERN.search(text or "")) or tools.is_affirmative(text or "")


def detect_language(text: str) -> str | None:
    return "ar" if _ARABIC.search(text or "") else None


# --------------------------------------------------------------------------
# Aggregate
# --------------------------------------------------------------------------
@dataclass
class OrderDetails:
    name: str | None = None
    language: str | None = None
    city: str | None = None
    area: str | None = None
    address: str | None = None
    service_key: str | None = None
    service_label: str | None = None
    unit_type: str | None = None
    requires_manual_quote: bool = False
    items: list[dict] = field(default_factory=list)

    @property
    def service_id(self) -> str | None:
        """Canonical service id (same value as ``service_key`` — the JSON catalog
        uses ``service_id``/``key`` interchangeably)."""
        return self.service_key
    pickup_slot: str | None = None
    delivery_slot: str | None = None
    payment_method: str | None = None
    confirmed: bool = False

    def has_booking_details(self) -> bool:
        """Enough signal to warrant creating/updating a draft order at all."""
        return bool(
            self.service_key or self.items or self.area or self.address or self.pickup_slot
        )

    def is_confirmable(self) -> bool:
        """Minimum before a draft may be promoted past 'draft' on confirmation:
        a service (or items) AND somewhere to pick up from."""
        return bool((self.service_key or self.items) and (self.area or self.address))

    def customer_fields(self) -> dict:
        """Non-empty customer-profile fields, for customers_repo.update."""
        out: dict[str, object] = {}
        for key in ("name", "language", "city", "area", "address"):
            value = getattr(self, key)
            if value:
                out[key] = value
        return out


def _merge_items(existing: list[dict], new: list[dict]) -> list[dict]:
    by_name: dict[str, int] = {i["item"]: i["quantity"] for i in existing}
    for i in new:
        by_name[i["item"]] = i["quantity"]  # latest mention wins
    return [{"item": name, "quantity": qty} for name, qty in by_name.items()]


def extract_customer_order_details(
    text: str, context: OrderDetails | None = None
) -> OrderDetails:
    """Extract details from ``text`` and merge onto ``context`` (prior turns).

    Scalar fields: a non-empty value from this message overrides the prior one
    (lets a customer correct themselves). Items accumulate. ``confirmed`` always
    reflects THIS message (a stale 'yes' from an earlier turn is not sticky).
    """
    base = context or OrderDetails()

    area = tools.extract_area(text) or base.area
    city = _detect_city(text) or area_to_city(area) or base.city
    service_key = tools.extract_service_type(text) or base.service_key
    service_label = service_labels().get(service_key) if service_key else base.service_label
    service = service_by_id(service_key) if service_key else None
    unit_type = service.get("unit_type") if service else base.unit_type
    requires_manual_quote = (
        bool(service.get("requires_manual_quote")) if service else base.requires_manual_quote
    )
    address = extract_address(text, area=area) or base.address
    name = extract_name(text) or base.name
    language = detect_language(text) or base.language
    pickup_slot = tools.extract_time_hint(text) or base.pickup_slot
    delivery_slot = extract_delivery_slot(text) or base.delivery_slot
    payment_method = extract_payment_method(text) or base.payment_method
    items = _merge_items(base.items, extract_items(text))

    return OrderDetails(
        name=name,
        language=language,
        city=city,
        area=area,
        address=address,
        service_key=service_key,
        service_label=service_label,
        unit_type=unit_type,
        requires_manual_quote=requires_manual_quote,
        items=items,
        pickup_slot=pickup_slot,
        delivery_slot=delivery_slot,
        payment_method=payment_method,
        confirmed=is_confirmation(text),
    )


def accumulate_from_messages(customer_texts: list[str]) -> OrderDetails:
    """Fold a whole customer-message history (oldest first) into one
    ``OrderDetails``. The final ``confirmed`` reflects the LAST message only."""
    details = OrderDetails()
    for text in customer_texts:
        details = extract_customer_order_details(text, details)
    return details
