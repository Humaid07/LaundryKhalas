"""Small deterministic helpers the agent uses before/around the LLM call.
Not a classifier module - just enough lightweight slot-extraction and
pricing lookup to keep the LLM from having to invent facts.
"""
import difflib
import re

from agents.whatsapp_agent.prompts import load_knowledge
from rules import service_catalog

# Service keywords and label->key map are both built from the configured
# catalog in config/laundry_services.json - edit services there, not here.
_SERVICE_KEYWORDS = {s["key"]: s["keywords"] for s in service_catalog()}

# The exact quick-reply chip / dropdown option labels sent verbatim by the
# UI (apps/whatsapp-chat/lib/constants.ts SERVICE_OPTIONS). Checked before
# the loose keyword lists so a chip click always resolves to exactly the
# service the customer picked, with zero ambiguity.
_SERVICE_LABEL_TO_KEY = {s["label"].lower(): s["key"] for s in service_catalog()}

_INTENT_KEYWORDS = {
    "pricing_question": ["price", "cost", "how much", "rate", "charge"],
    "area_question": ["do you cover", "service area", "area you", "which areas"],
    "track_order_request": [
        "status of my order", "track my order", "track order", "where is my order",
    ],
    "cancel_order_request": ["cancel my order", "cancel order"],
    "change_pickup_time_request": [
        "change my pickup time", "change pickup time", "reschedule my pickup",
        "reschedule pickup", "change my pickup",
    ],
    "add_items_request": [
        "add more items", "add items", "add another item", "add to my order",
    ],
    "call_support_request": [
        "speak to support", "speak to a human", "speak to someone", "talk to a human",
        "talk to support", "call support", "customer support", "human agent",
        "speak to an agent", "speak to a person",
    ],
    "complaint_placeholder": ["complain", "refund", "terrible", "bad service", "unhappy", "angry"],
    "new_pickup_request": ["pickup", "pick up", "pick-up", "collect my", "schedule a", "book a"],
}

_GREETING_PATTERN = re.compile(
    r"^\s*(hi+|hello+|hey+|hiya|yo|good\s?(morning|afternoon|evening)|"
    r"(as)?salam(u)?\s?(a)?laikum|greetings)[\s!.,]*$",
    re.IGNORECASE,
)
_THANKS_PATTERN = re.compile(
    r"^\s*(thanks|thank\s?you|thankyou|thx|ty|shukran|appreciate\s?it)[\s!.,]*$",
    re.IGNORECASE,
)
_FAREWELL_PATTERN = re.compile(
    r"^\s*(bye|goodbye|good\s?bye|see\s?you|take\s?care|have\s?a\s?good\s?day)[\s!.,]*$",
    re.IGNORECASE,
)
_AFFIRMATIVE_PATTERN = re.compile(
    r"^\s*(yes+|yeah+|yep+|yup+|sure|ok(ay)?|sounds\s?good|please\s?do|go\s?ahead|"
    r"correct|that'?s\s?right|confirm(ed)?)[\s!.,]*$",
    re.IGNORECASE,
)
_NEGATIVE_PATTERN = re.compile(
    r"^\s*(no+|nope|not\s?(now|really|yet)|no\s?thanks|not\s?interested)[\s!.,]*$",
    re.IGNORECASE,
)
_QUESTION_WORDS = (
    "what", "how", "when", "where", "why", "which", "who",
    "can", "could", "do", "does", "did", "is", "are", "will", "would", "should",
)


def is_greeting(text: str) -> bool:
    return bool(_GREETING_PATTERN.match(text.strip()))


def is_thanks(text: str) -> bool:
    return bool(_THANKS_PATTERN.match(text.strip()))


def is_farewell(text: str) -> bool:
    return bool(_FAREWELL_PATTERN.match(text.strip()))


def is_affirmative(text: str) -> bool:
    return bool(_AFFIRMATIVE_PATTERN.match(text.strip()))


def is_negative(text: str) -> bool:
    return bool(_NEGATIVE_PATTERN.match(text.strip()))


def is_question(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if stripped.endswith("?"):
        return True
    first_word = re.split(r"\s+", stripped, maxsplit=1)[0].strip("?.,!").lower()
    return first_word in _QUESTION_WORDS


def detect_intent(text: str) -> str:
    if is_greeting(text):
        return "greeting"
    if is_thanks(text):
        return "smalltalk_thanks"
    if is_farewell(text):
        return "smalltalk_farewell"
    if is_affirmative(text):
        return "confirmation_yes"
    if is_negative(text):
        return "confirmation_no"
    lowered = text.lower().strip()
    if lowered in _SERVICE_LABEL_TO_KEY:
        return "new_pickup_request"
    for intent, keywords in _INTENT_KEYWORDS.items():
        if any(kw in lowered for kw in keywords):
            return intent
    if any(kw in lowered for services in _SERVICE_KEYWORDS.values() for kw in services):
        return "service_question"
    if is_question(text):
        return "unanswerable_question"
    return "unknown_laundry_related"


def extract_service_type(text: str) -> str | None:
    lowered = text.lower().strip()
    if lowered in _SERVICE_LABEL_TO_KEY:
        return _SERVICE_LABEL_TO_KEY[lowered]
    for service, keywords in _SERVICE_KEYWORDS.items():
        if any(kw in lowered for kw in keywords):
            return service
    return None


def _load_service_areas() -> tuple[list[str], dict[str, str]]:
    """Builds (matchable phrases, lowercase->canonical-display map) from
    config/laundrykhalas_knowledge.json's "service_areas" section - all 7
    emirates plus Qatar, editable there with no code change. Read once at
    import time (rebuilding a ~150-phrase regex on every message would be
    wasteful given accumulate_slots calls this per history turn) - restart
    the service after editing the config to pick up area changes."""
    kb = load_knowledge()
    areas_cfg = kb.get("service_areas", {})
    display_map: dict[str, str] = {}
    for key, value in areas_cfg.items():
        if key in ("note", "aliases"):
            continue
        for area in value:
            display_map[area.lower()] = area
    for alias, canonical in areas_cfg.get("aliases", {}).items():
        display_map[alias.lower()] = canonical
    phrases = sorted(display_map.keys(), key=len, reverse=True)
    return phrases, display_map


_AREA_PHRASES, _AREA_DISPLAY_MAP = _load_service_areas()
# Longer/more specific phrases first (already sorted above) so a multi-word
# area isn't cut short by a shorter alternative matching at the same spot.
_AREA_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(p) for p in _AREA_PHRASES) + r")\b", re.IGNORECASE
)

# Fallback for a real area not in the gazetteer at all: "in/at/near/from
# <Capitalized Phrase>" - conservative (title case required) to avoid
# false-positives on ordinary lowercase words, filtered against a stoplist.
_AREA_FALLBACK_PATTERN = re.compile(
    r"\b(?:in|at|near|from)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,2})\b"
)
_AREA_FALLBACK_STOPWORDS = {
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "today", "tomorrow", "tonight", "morning", "afternoon", "evening",
    "this week", "next week", "the morning", "the afternoon", "the evening",
    "my", "your", "our", "the", "case", "addition", "general",
}

_AREA_WORD_PATTERN = re.compile(r"[a-zA-Z']+")


def _fuzzy_match_area(text: str, *, cutoff: float = 0.82) -> str | None:
    """Typo tolerance (e.g. "dubi marina" -> "dubai marina"): compares every
    1-3 word window of the message against the known area phrases using
    difflib, and returns the closest match above `cutoff`. Only candidates
    of 4+ characters are considered, to avoid short words fuzzy-matching
    into an unrelated short area name by chance.
    """
    words = _AREA_WORD_PATTERN.findall(text.lower())
    candidates = [
        " ".join(words[i : i + n])
        for n in (3, 2, 1)
        for i in range(len(words) - n + 1)
    ]

    best_phrase, best_ratio = None, 0.0
    for candidate in candidates:
        if len(candidate) < 4:
            continue
        matches = difflib.get_close_matches(candidate, _AREA_PHRASES, n=1, cutoff=cutoff)
        if not matches:
            continue
        ratio = difflib.SequenceMatcher(None, candidate, matches[0]).ratio()
        if ratio > best_ratio:
            best_phrase, best_ratio = matches[0], ratio
    return best_phrase


def extract_area(text: str) -> str | None:
    match = _AREA_PATTERN.search(text)
    if match:
        return _AREA_DISPLAY_MAP[match.group(1).lower()]

    fuzzy = _fuzzy_match_area(text)
    if fuzzy:
        return _AREA_DISPLAY_MAP[fuzzy]

    fallback = _AREA_FALLBACK_PATTERN.search(text)
    if fallback and fallback.group(1).lower() not in _AREA_FALLBACK_STOPWORDS:
        return fallback.group(1).title()
    return None


_CLOCK_TIME_PATTERN = re.compile(
    r"\b\d{1,2}(:\d{2})?\s?(am|pm)\b|\b([01]?\d|2[0-3]):[0-5]\d\b", re.IGNORECASE
)
_TIME_WORD_PATTERN = re.compile(
    r"\b(today|tomorrow|tonight|morning|afternoon|evening|this week|next week|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    re.IGNORECASE,
)


def extract_time_hint(text: str) -> str | None:
    clock_match = _CLOCK_TIME_PATTERN.search(text)
    if clock_match:
        return clock_match.group(0).strip().lower()
    word_match = _TIME_WORD_PATTERN.search(text)
    return word_match.group(1).lower() if word_match else None


def lookup_price(service_type: str) -> dict | None:
    """Configured price for a service key, or None if no price is set yet
    (in which case the agent must not invent one - RULE 7)."""
    for service in service_catalog():
        if service["key"] == service_type:
            return service.get("pricing")
    return None


# Order-id shapes, tried in order at each position: the full LK-AE-1024
# business format first (so the whole id is captured, not just its trailing
# number), then looser LK1023 / #1024 / "order 1024" / bare 4+ digit forms.
_ORDER_ID_PATTERN = re.compile(
    r"\bLK-[A-Za-z]{1,3}-\d{2,6}\b"
    r"|\bLK-?[A-Za-z0-9]{3,}\b"
    r"|#\s?\d{3,}"
    r"|\border\s*#?\s*\d{3,}\b"
    r"|\b\d{4,}\b",
    re.IGNORECASE,
)


def extract_order_id(text: str) -> str | None:
    match = _ORDER_ID_PATTERN.search(text)
    return match.group(0).strip() if match else None


# Markers the agent leaves in its own follow-up questions so a bare reply on
# the next turn routes back into the right flow without separate state.
BOOKING_ITEMS_MARKER = "share the item details"
CANCEL_CONFIRM_MARKER = "send a cancellation request"


def last_agent_asked(history: list[tuple[str, str]], marker: str) -> bool:
    """True if the most recent message was the agent and contained `marker`."""
    if not history:
        return False
    role, content = history[-1]
    return role == "agent" and marker.lower() in content.lower()


# Each order-flow follow-up-asking reply (see llm/providers/mock.py)
# contains one of these substrings verbatim - used to recognize "the
# customer is now answering that question" on the next turn without
# needing separate conversation-state storage. Checked most-specific-first.
_PENDING_ACTION_MARKERS = [
    ("cancel_order_request", "still be cancelled"),
    ("change_pickup_time_request", "new pickup time you prefer"),
    ("track_order_request", "help you check the status"),
    ("add_items_request", "items you would like to add"),
]


def pending_order_action(history: list[tuple[str, str]]) -> str | None:
    """If the last message in the conversation was the agent asking a
    track/cancel/change-time/add-items follow-up question, returns which
    action it was for - so a bare reply like "LK-1023" or "2 more shirts"
    (no other keywords) still resolves correctly instead of falling through
    to "unknown_laundry_related"."""
    if not history:
        return None
    role, content = history[-1]
    if role != "agent":
        return None
    lowered = content.lower()
    for action, marker in _PENDING_ACTION_MARKERS:
        if marker in lowered:
            return action
    return None


def accumulate_slots(
    history: list[tuple[str, str]], text: str
) -> dict[str, str | None]:
    """Scans every customer turn (oldest first) plus the current message for
    service/area/time, so a detail given two messages ago isn't forgotten.
    A later mention overrides an earlier one (lets a customer correct
    themselves), and the current message always has final say.
    """
    service_type: str | None = None
    area: str | None = None
    time_hint: str | None = None

    for role, content in history:
        if role != "customer":
            continue
        service_type = extract_service_type(content) or service_type
        area = extract_area(content) or area
        time_hint = extract_time_hint(content) or time_hint

    service_type = extract_service_type(text) or service_type
    area = extract_area(text) or area
    time_hint = extract_time_hint(text) or time_hint

    return {"service_type": service_type, "area": area, "time_hint": time_hint}
