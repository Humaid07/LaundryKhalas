"""Deterministic slot extraction for order collection and natural follow-ups.

Pulls name, area, service, items (with quantities), pickup date/time and payment
method out of free text. Kept intentionally conservative — it never guesses a
price (that always goes through knowledge_base.find_price) and never fabricates a
field it cannot see in the message.
"""
from __future__ import annotations

import re

from laundry_class import knowledge_base as kb

# ---------------------------------------------------------------------------
# Areas (supported list mirrors the KB pickup/delivery table; testing values).
# ---------------------------------------------------------------------------
_AREA_ALIASES = {
    "jlt": "Jumeirah Lake Towers",
    "marina": "Dubai Marina",
    "downtown": "Downtown Dubai",
    "dso": "Dubai Silicon Oasis",
    "business bay": "Business Bay",
    "al barsha": "Al Barsha",
    "barsha": "Al Barsha",
    "deira": "Deira",
    "bur dubai": "Bur Dubai",
    "international city": "International City",
    "jumeirah lake towers": "Jumeirah Lake Towers",
    "dubai marina": "Dubai Marina",
    "jumeirah": "Jumeirah",
    "downtown dubai": "Downtown Dubai",
    "dubai silicon oasis": "Dubai Silicon Oasis",
}
# Longest phrases first so "dubai marina" is matched before "marina".
_AREA_KEYS = sorted(_AREA_ALIASES.keys(), key=len, reverse=True)


def extract_area(text: str) -> str | None:
    lowered = text.lower()
    for key in _AREA_KEYS:
        if re.search(rf"\b{re.escape(key)}\b", lowered):
            return _AREA_ALIASES[key]
    return None


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------
_SERVICE_PATTERNS = [
    ("Dry Cleaning", ["dry clean", "dry-clean", "dry cleaning"]),
    ("Wash and Iron", ["wash and iron", "wash & iron", "wash and press", "wash & press"]),
    ("Ironing Only", ["iron only", "ironing only", "just iron", "just press", "press only", "ironing"]),
    ("Wash and Fold", ["wash and fold", "wash & fold", "wash fold", "washing and folding"]),
]


def extract_service(text: str) -> str | None:
    lowered = text.lower()
    for service, patterns in _SERVICE_PATTERNS:
        if any(p in lowered for p in patterns):
            return service
    return None


# ---------------------------------------------------------------------------
# Name
# ---------------------------------------------------------------------------
# Case-insensitive trigger; the name itself is captured as free words and then
# trimmed at the first connector, so "my name is Maya and I'm in JLT" -> "Maya".
_NAME_PATTERNS = [
    re.compile(r"\bmy name is\s+([a-zA-Z'’ -]+)", re.IGNORECASE),
    re.compile(r"\bi am\s+([a-zA-Z'’ -]+)", re.IGNORECASE),
    re.compile(r"\bi'?m\s+([a-zA-Z'’ -]+)", re.IGNORECASE),
    re.compile(r"\bthis is\s+([a-zA-Z'’ -]+)", re.IGNORECASE),
    re.compile(r"\bname'?s\s+([a-zA-Z'’ -]+)", re.IGNORECASE),
]
_NAME_CONNECTORS = {
    "and", "in", "at", "from", "here", "im", "i", "the", "a", "an", "my", "on",
    "with", "for", "to", "of", "but", "so", "who", "that", "please",
}
_NAME_STOPWORDS = {
    "not", "very", "really", "still", "looking", "interested", "trying", "hoping",
    "sorry", "okay", "ok", "just", "calling", "wondering",
}


def extract_name(text: str) -> str | None:
    for pat in _NAME_PATTERNS:
        m = pat.search(text)
        if not m:
            continue
        words: list[str] = []
        for w in m.group(1).split():
            wl = w.strip(".,!?").lower()
            if wl in _NAME_CONNECTORS:
                break
            words.append(w.strip(".,!?"))
            if len(words) == 2:
                break
        if not words:
            continue
        if words[0].lower() in _NAME_STOPWORDS:
            continue
        return " ".join(w.capitalize() for w in words)
    return None


# ---------------------------------------------------------------------------
# Address (conservative — only fires with an explicit trigger + address word)
# ---------------------------------------------------------------------------
_ADDRESS_KEYWORDS = re.compile(
    r"(apartment|apt|villa|tower|building|flat|cluster|residence|street|road|floor)",
    re.IGNORECASE,
)
_ADDRESS_TAIL = re.compile(
    r"\s*(?:,?\s*(?:tomorrow|today|tonight|next week|this week)\b|,?\s*at\s+\d|\s+\d{1,2}\s?(?:am|pm)\b).*$",
    re.IGNORECASE,
)


def extract_address(text: str) -> str | None:
    m = re.search(r"\b(?:address is|address:|collected from|pick(?:ed)? up from|from|at)\s+(.+)$",
                  text, re.IGNORECASE)
    candidate = None
    if m and _ADDRESS_KEYWORDS.search(m.group(1)):
        candidate = m.group(1)
    elif _ADDRESS_KEYWORDS.search(text) and re.search(r"\d", text):
        # bare address like "Marina Heights, Apartment 304"
        candidate = text
    if not candidate:
        return None
    candidate = _ADDRESS_TAIL.sub("", candidate).strip().rstrip(".,")
    return candidate or None


# ---------------------------------------------------------------------------
# Items with quantities
# ---------------------------------------------------------------------------
_NUMBER_WORDS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
}
# quantity (digit or word) + item phrase (1-3 words)
_ITEM_PATTERN = re.compile(
    r"\b(\d+|a|an|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+"
    r"([a-zA-Z][a-zA-Z\- ]*?)(?=\s+(?:and|,|for|from|in|at|to|with|please)\b|[,.?!;:]|$)",
    re.IGNORECASE,
)
_ITEM_NOISE = {
    "am", "pm", "oclock", "o'clock", "kg", "kilos", "kilograms", "shirts for",
    "minute", "minutes", "hour", "hours", "days", "day", "week", "weeks",
    "pm today", "am today", "pm tomorrow", "am tomorrow",
    # order/logistics words that look like "a <noun>" but are not garments
    "laundry", "pickup", "pick up", "laundry pickup", "order", "collection",
    "appointment", "slot", "number", "person", "human", "refund", "quote",
    "estimate", "price", "time", "date", "delivery",
}


def extract_items(text: str) -> list[dict]:
    """List of {raw, item, quantity, priced(bool)}. `item` is the canonical KB
    label when the item is in the price table, else the raw phrase. Never prices
    here — the graph does that via knowledge_base.find_price so an unknown item
    is surfaced honestly."""
    items: list[dict] = []
    for m in _ITEM_PATTERN.finditer(text):
        qty_raw, phrase = m.group(1).lower(), m.group(2).strip().lower()
        phrase = re.sub(r"\s+", " ", phrase)
        # strip a leading copula so "one is an evening gown" -> "evening gown"
        phrase = re.sub(r"^(is|are)\s+(a|an|the)\s+", "", phrase).strip()
        if not phrase or phrase in _ITEM_NOISE or len(phrase) < 2:
            continue
        # drop trailing filler words
        phrase = re.sub(r"\b(please|thanks|thank you)\b", "", phrase).strip()
        if not phrase:
            continue
        qty = int(qty_raw) if qty_raw.isdigit() else _NUMBER_WORDS.get(qty_raw, 1)
        entry = kb.find_price(phrase)
        items.append({
            "raw": phrase,
            "item": entry.item if entry else phrase,
            "quantity": qty,
            "priced": entry is not None and not entry.inspection_required,
        })

    # Wash & Fold bags are written digit-glued ("6kg bag", "12kg") so the general
    # quantity+noun pattern above misses them — detect them explicitly.
    already = {i["raw"] for i in items}
    for bm in re.finditer(r"\b(\d+)\s?kg\b", text, re.IGNORECASE):
        label = "6kg bag" if int(bm.group(1)) <= 6 else "12kg bag"
        if label not in already:
            entry = kb.find_price(label)
            items.append({"raw": label, "item": entry.item if entry else label,
                          "quantity": 1, "priced": entry is not None})
            already.add(label)
    if not items and re.search(r"\bbags?\b", text, re.IGNORECASE):
        entry = kb.find_price("6kg bag")
        items.append({"raw": "6kg bag", "item": entry.item if entry else "6kg bag",
                      "quantity": 1, "priced": entry is not None})
    return items


# ---------------------------------------------------------------------------
# Pickup date / time
# ---------------------------------------------------------------------------
_CLOCK = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s?(am|pm)\b", re.IGNORECASE)
_AT_HOUR = re.compile(r"\bat\s+(\d{1,2})(?::(\d{2}))?\b", re.IGNORECASE)
_DAY_WORDS = re.compile(
    r"\b(today|tomorrow|tonight|day after tomorrow|this week|next week|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    re.IGNORECASE,
)
_PART_OF_DAY = re.compile(r"\b(morning|afternoon|evening|noon|midday)\b", re.IGNORECASE)


def _normalize_hour(hour: int, meridiem: str | None, part: str | None) -> str:
    if meridiem:
        return f"{hour}:00 {meridiem.upper()}" if False else f"{hour} {meridiem.upper()}"
    # infer AM/PM from part of day when no meridiem was given
    if part in ("evening", "afternoon") and hour < 12:
        return f"{hour}:00 PM"
    if part == "morning" and hour <= 12:
        return f"{hour}:00 AM"
    # bare hour, no context: assume a sensible daytime reading
    if hour <= 7:
        return f"{hour}:00 PM"
    return f"{hour}:00 AM"


def extract_time(text: str, *, expecting_time: bool = False) -> str | None:
    """Return a human pickup-time string, or None.

    `expecting_time=True` means the agent's previous message asked for a time, so a
    bare number ("10", "at 6") is interpreted as an hour rather than a quantity —
    this is what makes short replies like "10" resolve to 10 o'clock from context.
    """
    part_m = _PART_OF_DAY.search(text)
    part = part_m.group(1).lower() if part_m else None
    day_m = _DAY_WORDS.search(text)
    day = day_m.group(1).lower() if day_m else None

    clock = _CLOCK.search(text)
    if clock:
        hour = int(clock.group(1))
        mins = clock.group(2)
        mer = clock.group(3).upper()
        time_str = f"{hour}:{mins} {mer}" if mins else f"{hour} {mer}"
        return _join_day_time(day, time_str)

    at = _AT_HOUR.search(text)
    if at:
        time_str = _normalize_hour(int(at.group(1)), None, part)
        return _join_day_time(day, time_str)

    if expecting_time:
        bare = re.search(r"\b(\d{1,2})\b", text)
        if bare:
            time_str = _normalize_hour(int(bare.group(1)), None, part)
            return _join_day_time(day, time_str)

    if day or part:
        pieces = [p for p in (day, part) if p]
        return " ".join(pieces)
    return None


def _join_day_time(day: str | None, time_str: str) -> str:
    return f"{day} at {time_str}" if day else time_str


# ---------------------------------------------------------------------------
# Payment
# ---------------------------------------------------------------------------
def extract_payment(text: str) -> str | None:
    lowered = text.lower()
    if re.search(r"\bcash\b", lowered):
        return "Cash on delivery"
    if re.search(r"\bcard\b", lowered):
        return "Card on delivery"
    if "online" in lowered or "payment link" in lowered or "link" in lowered:
        return "Online payment link"
    return None


# ---------------------------------------------------------------------------
# Order id
# ---------------------------------------------------------------------------
_ORDER_ID = re.compile(r"\bLC-?TEST-?\d{3,}\b|\bLC-[A-Za-z]{1,3}-\d{2,}\b|#?\s?\d{4,}\b", re.IGNORECASE)


def extract_order_id(text: str) -> str | None:
    m = _ORDER_ID.search(text)
    if not m:
        return None
    raw = m.group(0).strip().lstrip("#").strip()
    # normalize LCTEST1004 / LC-TEST 1004 -> LC-TEST-1004
    digits = re.sub(r"\D", "", raw)
    if raw.upper().replace("-", "").replace(" ", "").startswith("LCTEST") and digits:
        return f"LC-TEST-{digits}"
    return raw
