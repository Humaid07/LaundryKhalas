"""Operational priority for a structured order note (pure, deterministic).

Priority controls how strongly a note is surfaced on the facility order card:

* ``CRITICAL`` — genuinely blocking / safety / do-not-proceed information
  (existing damage, "do not process until approved", allergy/chemical
  restriction, "do not alter" a section, awaiting revised-price approval).
* ``IMPORTANT`` — needs attention before/while processing but not blocking
  (inspection required, special care, stains, luxury/designer handling).
* ``NORMAL`` — routine instruction.

An explicitly stored priority (anything other than the ``NORMAL`` default) always
wins; otherwise it is DERIVED from the note's category + keywords. This is a
grounded classification over the note's own structured fields — it never invents
content, it only ranks what the customer/ops already said.
"""

from __future__ import annotations

PRIORITIES = ("NORMAL", "IMPORTANT", "CRITICAL")
_RANK = {"NORMAL": 0, "IMPORTANT": 1, "CRITICAL": 2}

# Categories that are inherently at least IMPORTANT.
_IMPORTANT_CATEGORIES = frozenset({
    "EXISTING_DAMAGE", "INSPECTION_REQUIREMENT", "SPECIAL_CARE", "STAIN_NOTE",
})

# Keyword → priority. Checked against the lowered note text; longest signal wins.
_CRITICAL_KEYWORDS = (
    "do not process", "don't process", "do not proceed", "hold until",
    "await approval", "awaiting approval", "not approved", "pending approval",
    "do not alter", "don't alter", "do not cut", "do not wash", "do not clean",
    "allergy", "allergic", "chemical restriction", "no chemicals", "no bleach",
    "hazard", "biohazard", "do not tumble", "hand wash only and fragile",
)
_IMPORTANT_KEYWORDS = (
    "inspect", "inspection", "fragile", "handle with care", "delicate",
    "designer", "luxury", "leather", "suede", "silk", "cashmere", "wedding",
    "dry clean only", "hand wash only", "stain", "damage", "scratch", "tear",
    "loose thread", "measure", "measurement",
)


def normalize_priority(value: str | None) -> str:
    """Coerce an untrusted priority to a valid value, defaulting to NORMAL."""
    v = (value or "").strip().upper()
    return v if v in _RANK else "NORMAL"


def _keyword_priority(text: str) -> str:
    low = (text or "").lower()
    if any(kw in low for kw in _CRITICAL_KEYWORDS):
        return "CRITICAL"
    if any(kw in low for kw in _IMPORTANT_KEYWORDS):
        return "IMPORTANT"
    return "NORMAL"


def classify(category: str | None, text: str | None, *, explicit: str | None = None) -> str:
    """Return the effective priority for one note.

    An explicit non-NORMAL stored priority is authoritative. Otherwise derive the
    highest of the category-floor and the keyword signal.
    """
    stored = normalize_priority(explicit)
    if stored != "NORMAL":
        return stored
    cat = (category or "").strip().upper()
    category_floor = "IMPORTANT" if cat in _IMPORTANT_CATEGORIES else "NORMAL"
    keyword = _keyword_priority(text or "")
    # Existing damage that also reads as blocking becomes CRITICAL via keywords;
    # otherwise EXISTING_DAMAGE stays IMPORTANT (visible, not blocking).
    best = category_floor
    if _RANK[keyword] > _RANK[best]:
        best = keyword
    return best


def is_critical(category: str | None, text: str | None, *, explicit: str | None = None) -> bool:
    return classify(category, text, explicit=explicit) == "CRITICAL"
