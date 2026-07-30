"""Structured additional-order-notes engine (backend-authoritative).

Claude *proposes* candidate notes from the conversation; this module validates
them, de-duplicates them, applies PATCH semantics (never erase on empty), handles
corrections (supersede within single-value categories) and removals, and builds
the immutable confirmed snapshot.

Pure functions over plain dicts/lists — no DB — so the whole policy is
unit-testable. The asyncpg persistence lives in db/repositories/order_notes_repo.py
and calls into these helpers.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import Enum

# --- Categories ------------------------------------------------------------

CATEGORIES: tuple[str, ...] = (
    "PICKUP_INSTRUCTION",
    "DELIVERY_INSTRUCTION",
    "ACCESS_INSTRUCTION",
    "CONTACT_PREFERENCE",
    "TIMING_PREFERENCE",
    "ITEM_HANDLING",
    "STAIN_NOTE",
    "EXISTING_DAMAGE",
    "SPECIAL_CARE",
    "FACILITY_INSTRUCTION",
    "INSPECTION_REQUIREMENT",
    "OTHER_OPERATIONAL_NOTE",
)
_CATEGORY_SET = frozenset(CATEGORIES)

# Categories that hold ONE current value — a new note in these supersedes the
# previous active one (a correction), rather than piling up.
SINGLE_VALUE_CATEGORIES = frozenset({"CONTACT_PREFERENCE", "TIMING_PREFERENCE"})

# Human-facing section grouping for summaries + the facility dashboard.
CATEGORY_LABELS: dict[str, str] = {
    "PICKUP_INSTRUCTION": "Pickup Instructions",
    "DELIVERY_INSTRUCTION": "Delivery Instructions",
    "ACCESS_INSTRUCTION": "Building & Access Instructions",
    "CONTACT_PREFERENCE": "Contact Preferences",
    "TIMING_PREFERENCE": "Timing Preferences",
    "ITEM_HANDLING": "Item Handling",
    "STAIN_NOTE": "Stains",
    "EXISTING_DAMAGE": "Existing Damage",
    "SPECIAL_CARE": "Special Care",
    "FACILITY_INSTRUCTION": "Facility Instructions",
    "INSPECTION_REQUIREMENT": "Inspection Requirements",
    "OTHER_OPERATIONAL_NOTE": "Other Notes",
}

_MAX_TEXT_LEN = 300

# Casual / non-operational phrases that must never become notes even if proposed.
_NON_OPERATIONAL = (
    "thank", "thanks", "thankyou", "welcome", "great", "awesome", "perfect", "cool",
    "hello", "hi", "hey", "good morning", "good evening", "good night", "ok", "okay",
    "sure", "nice", "very helpful", "appreciate", "cheers", "bye",
)
# Single-word casual openers — a note that STARTS with one of these and carries no
# operational keyword is chatter, not an instruction (e.g. "Thanks, you're helpful").
_CASUAL_OPENERS = {
    "thank", "thanks", "thankyou", "hi", "hello", "hey", "ok", "okay", "great",
    "awesome", "perfect", "cool", "nice", "welcome", "cheers", "bye", "sure", "good",
}
# Operational signal words — presence keeps a note even if it opens casually.
_OPERATIONAL_WORDS = {
    "collect", "reception", "security", "concierge", "elevator", "lift", "floor",
    "apartment", "flat", "room", "parking", "ring", "bell", "call", "whatsapp",
    "message", "fragile", "careful", "carefully", "handle", "stain", "damage",
    "scratch", "separate", "fold", "hanger", "hangers", "inspect", "colour", "color",
    "deliver", "delivery", "pickup", "gate", "door", "building", "villa", "mix",
    "iron", "suit", "garment", "shirt", "before", "after", "pm", "am", "leave",
    "return", "wash", "dry", "reach", "arrive", "arrives", "contact",
}

# Guarantee-style promises we must not store as facts (store the *request* instead).
_PROMISE_RE = re.compile(r"\b(guarantee[d]?|guaranteed to|we will definitely|promise[d]?)\b", re.I)


class NoteStatus(str, Enum):
    ACTIVE = "ACTIVE"
    REMOVED = "REMOVED"
    SUPERSEDED = "SUPERSEDED"


def normalize_note_text(text: str | None) -> str:
    """Lowercased, whitespace-collapsed, trailing-punctuation-stripped key text."""
    t = (text or "").strip().lower()
    t = re.sub(r"\s+", " ", t)
    t = re.sub(r"[.!,;:\-\s]+$", "", t)
    return t


def dedupe_key(order_id: str, category: str, text: str) -> str:
    basis = f"{order_id}|{category}|{normalize_note_text(text)}"
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()


# --- Validation ------------------------------------------------------------

@dataclass(frozen=True)
class NoteValidation:
    ok: bool
    reason: str
    category: str = ""
    text: str = ""


def validate_order_note(category: str | None, text: str | None) -> NoteValidation:
    """Backend gate before a proposed note may be persisted."""
    cat = (category or "").strip().upper()
    body = (text or "").strip()
    if cat not in _CATEGORY_SET:
        return NoteValidation(False, "invalid_category")
    if not body:
        return NoteValidation(False, "empty_text")
    if len(body) > _MAX_TEXT_LEN:
        return NoteValidation(False, "too_long")
    if not any(ch.isalpha() for ch in body):
        return NoteValidation(False, "no_letters")
    norm = normalize_note_text(body)
    words = re.findall(r"\w+", norm)  # word tokens without punctuation ("thanks," -> "thanks")
    has_operational = any(w in _OPERATIONAL_WORDS for w in words)
    opens_casually = bool(words) and words[0] in _CASUAL_OPENERS
    if norm in _NON_OPERATIONAL or (opens_casually and not has_operational):
        return NoteValidation(False, "not_operational")
    if _PROMISE_RE.search(body):
        # Never let an unconfirmed guarantee be stored as a commitment.
        return NoteValidation(False, "unverified_promise")
    return NoteValidation(True, "ok", cat, body)


# --- Merge / PATCH ---------------------------------------------------------

class MergeAction(str, Enum):
    ADD = "add"
    DUPLICATE = "duplicate"          # identical active note already exists — no-op
    SUPERSEDE = "supersede"          # replaces an existing active note (correction)
    REJECTED = "rejected"            # failed validation


@dataclass
class MergePlan:
    action: MergeAction
    reason: str = ""
    category: str = ""
    text: str = ""
    dedupe: str = ""
    supersedes_id: str | None = None  # id of the active note being replaced


def _active(existing: list[dict]) -> list[dict]:
    return [n for n in existing if str(n.get("status", "ACTIVE")).upper() == "ACTIVE"]


def plan_note_merge(order_id: str, existing: list[dict], category: str | None, text: str | None) -> MergePlan:
    """Decide how one proposed note should be applied against existing notes."""
    v = validate_order_note(category, text)
    if not v.ok:
        return MergePlan(MergeAction.REJECTED, reason=v.reason)

    key = dedupe_key(order_id, v.category, v.text)
    actives = _active(existing)

    # Exact duplicate (same category + normalized text) already active → no-op.
    for n in actives:
        if n.get("dedupe_key") == key or (
            str(n.get("category", "")).upper() == v.category
            and normalize_note_text(n.get("text")) == normalize_note_text(v.text)
        ):
            return MergePlan(MergeAction.DUPLICATE, reason="duplicate", category=v.category, text=v.text, dedupe=key)

    # Single-value category → replace the existing active note (a correction).
    if v.category in SINGLE_VALUE_CATEGORIES:
        for n in actives:
            if str(n.get("category", "")).upper() == v.category:
                return MergePlan(
                    MergeAction.SUPERSEDE, reason="correction", category=v.category,
                    text=v.text, dedupe=key, supersedes_id=str(n.get("id") or n.get("note_id")),
                )

    return MergePlan(MergeAction.ADD, reason="new", category=v.category, text=v.text, dedupe=key)


def plan_patch(order_id: str, existing: list[dict], candidates: list[dict] | None) -> list[MergePlan]:
    """PATCH semantics for a batch of proposals. A null/empty candidate list is a
    no-op and NEVER erases existing notes."""
    if not candidates:
        return []
    plans: list[MergePlan] = []
    working = list(existing)
    for cand in candidates:
        plan = plan_note_merge(order_id, working, cand.get("category"), cand.get("text"))
        plans.append(plan)
        if plan.action in (MergeAction.ADD, MergeAction.SUPERSEDE):
            # Reflect the applied note so later candidates in the same batch dedupe.
            if plan.supersedes_id:
                working = [n for n in working if str(n.get("id") or n.get("note_id")) != plan.supersedes_id]
            working = working + [{
                "id": f"pending-{len(working)}", "category": plan.category,
                "text": plan.text, "status": "ACTIVE", "dedupe_key": plan.dedupe,
            }]
    return plans


# --- Removal ---------------------------------------------------------------

def find_notes_to_remove(existing: list[dict], *, target_text: str | None = None, category: str | None = None) -> list[str]:
    """Return ids of ACTIVE notes matching a removal request (by keyword and/or
    category). Only clearly-matching notes are returned so unrelated notes stay."""
    actives = _active(existing)
    cat = (category or "").strip().upper() or None
    kw = normalize_note_text(target_text) if target_text else None
    out: list[str] = []
    for n in actives:
        nid = str(n.get("id") or n.get("note_id") or "")
        if not nid:
            continue
        ncat = str(n.get("category", "")).upper()
        ntext = normalize_note_text(n.get("text"))
        if cat and ncat != cat:
            continue
        if kw:
            # keyword must appear in the note (whole word or substring token match)
            if kw in ntext or any(tok in ntext.split() for tok in kw.split() if len(tok) > 2):
                out.append(nid)
        elif cat:
            out.append(nid)
    return out


# --- Grouping / snapshot ---------------------------------------------------

def group_active_by_category(existing: list[dict]) -> dict[str, list[str]]:
    """{category: [text, ...]} for ACTIVE notes, in the canonical category order."""
    grouped: dict[str, list[str]] = {}
    for cat in CATEGORIES:
        texts = [
            str(n.get("text", "")).strip()
            for n in _active(existing)
            if str(n.get("category", "")).upper() == cat and str(n.get("text", "")).strip()
        ]
        if texts:
            grouped[cat] = texts
    return grouped


def summary_lines(existing: list[dict]) -> list[str]:
    """Flat human-readable bullet texts for the customer order summary."""
    lines: list[str] = []
    for cat in CATEGORIES:
        for n in _active(existing):
            if str(n.get("category", "")).upper() == cat:
                t = str(n.get("text", "")).strip()
                if t:
                    lines.append(t)
    return lines


def build_confirmed_snapshot(existing: list[dict]) -> list[dict]:
    """Immutable snapshot of the ACTIVE notes at confirmation time."""
    return [
        {
            "note_id": str(n.get("id") or n.get("note_id") or ""),
            "category": str(n.get("category", "")).upper(),
            "text": str(n.get("text", "")).strip(),
            "source": n.get("source", "CUSTOMER_MESSAGE"),
            "confidence": n.get("confidence"),
        }
        for n in _active(existing)
    ]
