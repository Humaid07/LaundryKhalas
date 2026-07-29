"""Authoritative service-request classification (natural booking + unsupported
service handling).

Given a customer's free-text service phrase, decide what KIND of request it is
against the ACTIVE published catalogue. The BACKEND — never the model — is the
source of truth for whether a service is supported. Used by the Claude
``save_service_selection`` tool (agents/whatsapp_agent/booking_tools.py) so that:

  * a valid service / alias is persisted with a stable catalogue code;
  * an ambiguous laundry request (bare "ironing") triggers ONE clarification;
  * a clearly non-laundry request ("haircut", "taxi", "massage") is classified
    UNSUPPORTED so the agent politely declines, NEVER re-asks "which service"
    and NEVER erases an in-progress booking;
  * a bespoke / specialty laundry request ("heavily embroidered wedding dress")
    routes to the photo+location flow rather than an invented price.

Deterministic and offline: reads ``services.catalogue`` (and reuses the SAME
``services.booking_flow.resolve_service`` resolver the FSM uses, so validation
can't drift). No LLM, no DB.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

import structlog

from services import booking_flow as bf
from services import catalogue

logger = structlog.get_logger(__name__)


class ServiceKind(str, Enum):
    EXACT = "exact"              # resolves directly to a catalogue category
    ALIAS = "alias"             # resolves via a category/item alias
    AMBIGUOUS = "ambiguous"     # laundry, but needs one clarification (iron)
    BESPOKE = "bespoke"         # specialty laundry needing a photo/quote
    ROUTE = "route"             # route to a human specialist, never quote (spec §2.8)
    UNSUPPORTED = "unsupported"  # clearly NOT a Laundry Khalas service
    NONE = "none"               # empty / not service-related / unrecognisable

    @property
    def is_supported(self) -> bool:
        return self in (ServiceKind.EXACT, ServiceKind.ALIAS)


@dataclass(frozen=True)
class ServiceResolution:
    kind: ServiceKind
    category_code: str | None = None
    category_name: str | None = None
    reason: str = ""
    routing_category: str | None = None   # set when kind is ROUTE (spec §2.8)

    @property
    def is_supported(self) -> bool:
        return self.kind.is_supported


# Specialty / bespoke signals checked BEFORE catalogue resolution, so a phrase
# that would otherwise alias to a normal category (e.g. "wedding dress" → Clean &
# Press) is instead routed to the bespoke photo+quote flow when it carries a
# clear specialty marker. Kept deliberately NARROW so the real "Restoration"
# category and ordinary garments are not swept up.
_BESPOKE_SIGNALS: tuple[str, ...] = (
    "bespoke", "heavily embroidered", "embroidered", "embroidery", "beaded",
    "sequin", "couture", "custom-made", "custom made", "hand-made", "handmade",
    "invisible mending", "reweav", "re-weav", "re-dye", "redye",
    "leather repair", "leather restoration",
)

# Clearly non-laundry requests. Matched as whole words (so "spa" won't fire on
# "bag spa" — which anyway resolves in the catalogue first, and "cab" won't fire
# inside "cabinet"). Only consulted AFTER catalogue resolution fails, so anything
# the catalogue recognises is never mislabelled unsupported.
_UNSUPPORTED_TERMS: tuple[str, ...] = (
    "haircut", "hair cut", "hairdress", "hairstyl", "barber", "salon",
    "massage", "manicure", "pedicure", "nails", "nail art", "facial",
    "makeup", "make-up", "make up", "waxing", "threading", "eyebrow",
    "tattoo", "piercing", "spa day", "gym", "personal trainer", "yoga",
    "plumber", "plumbing", "electrician", "carpenter", "handyman",
    "car wash", "car service", "taxi", "cab ride", "grocery", "groceries",
    "restaurant", "catering", "food delivery", "pizza", "burger",
    "doctor", "dentist", "medicine", "pharmacy", "lawyer", "accountant",
    "photographer", "photography", "makeup artist", "dj ",
)

# Words that are safe to also flag when they appear on their own (short tokens
# that would be unsafe as bare substrings), matched with word boundaries.
_UNSUPPORTED_WORDS: tuple[str, ...] = (
    "haircut", "barber", "salon", "massage", "manicure", "pedicure", "facial",
    "makeup", "waxing", "tattoo", "piercing", "gym", "taxi", "grocery",
    "restaurant", "doctor", "dentist", "pharmacy", "lawyer", "yoga",
)


def _contains_term(low: str, terms: tuple[str, ...]) -> str | None:
    for term in terms:
        if term in low:
            return term
    return None


def _contains_word(low: str, words: tuple[str, ...]) -> str | None:
    for w in words:
        if re.search(rf"\b{re.escape(w)}\b", low):
            return w
    return None


def _is_unsupported(low: str) -> str | None:
    return _contains_term(low, _UNSUPPORTED_TERMS) or _contains_word(low, _UNSUPPORTED_WORDS)


def supported_categories() -> list[str]:
    """Human-readable list of the currently published service categories, for a
    polite "here's what we DO offer" line. Reads the live catalogue."""
    return [c["name"] for c in catalogue.categories()]


def classify_service_request(
    text: str | None,
    *,
    selection_id: str | None = None,
    has_active_service: bool = False,
) -> ServiceResolution:
    """Classify a free-text service phrase against the published catalogue.

    ``has_active_service`` is accepted so callers can log/branch on whether a
    booking is already in progress; it does not change the classification itself
    (a haircut is unsupported whether or not a booking exists — the CALLER decides
    to preserve the booking).
    """
    raw = (text or "").strip()
    low = raw.lower()
    if not raw and not selection_id:
        return ServiceResolution(ServiceKind.NONE, reason="empty")

    # 1) Route-to-human categories (villa/home cleaning, wedding dress, luxury/
    #    couture) win over BOTH the bespoke photo-flow and catalogue aliasing, so a
    #    "wedding dress" is handed to a specialist (spec §2.8) rather than quoted as
    #    Clean & Press. B2B is handled separately (services/b2b.py).
    from services import specialty_routing
    routed = specialty_routing.classify(low)
    if routed:
        return ServiceResolution(ServiceKind.ROUTE, reason=f"route:{routed.matched_term}",
                                 routing_category=routed.category)

    # 2) Specialty / bespoke marker wins over a plain alias resolution.
    sig = _contains_term(low, _BESPOKE_SIGNALS)
    if sig:
        return ServiceResolution(ServiceKind.BESPOKE, reason=f"bespoke_signal:{sig}")

    # 2) Authoritative catalogue resolution (same resolver as the FSM).
    code, reason = bf.resolve_service(bf.Inbound(text=raw, selection_id=selection_id))
    if reason == "ok" and code:
        cat = catalogue.category_by_code(code)
        name = cat["name"] if cat else code
        exact = low in (code.lower(), (name or "").lower())
        return ServiceResolution(
            ServiceKind.EXACT if exact else ServiceKind.ALIAS,
            category_code=code, category_name=name, reason="catalogue")
    if reason == "ambiguous":
        return ServiceResolution(ServiceKind.AMBIGUOUS, reason="ambiguous")

    # 3) Clearly non-laundry → unsupported (polite decline, never re-ask).
    term = _is_unsupported(low)
    if term:
        return ServiceResolution(ServiceKind.UNSUPPORTED, reason=f"non_laundry:{term}")

    # 4) Unrecognised laundry-ish text — ask the customer (show the categories).
    return ServiceResolution(ServiceKind.NONE, reason="unrecognised")
