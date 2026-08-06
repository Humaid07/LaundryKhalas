"""Deterministic "Required Work" builder (pure, grounded — never an LLM).

The Facility Dashboard leads every order card with a concise list of exactly what
the facility must do. That list is built HERE, only from structured order data:
the confirmed line items (name + quantity + service), the service type, and the
customer-confirmed structured notes (alteration instructions, inspection
requirements). No sentence is ever invented — each line is a mechanical rendering
of a field the customer or operations already confirmed.

If a short generated summary is ever introduced elsewhere, it must be validated
against ``build_required_work`` — the facility must never receive a work
instruction that Claude made up.
"""

from __future__ import annotations

# Service signal (substring of the service / item service label) → work verb.
# Longest, most specific signals first.
_VERB_SIGNALS: tuple[tuple[str, str], ...] = (
    ("wash and fold", "Wash & fold"),
    ("wash & fold", "Wash & fold"),
    ("wash and iron", "Wash & iron"),
    ("wash & iron", "Wash & iron"),
    ("dry clean", "Dry clean"),
    ("steam press", "Steam press"),
    ("press only", "Press"),
    ("iron", "Press"),
    ("press", "Press"),
    ("alteration", "Alter"),
    ("tailor", "Alter"),
    ("repair", "Repair"),
    ("restore", "Clean & restore"),
    ("restoration", "Clean & restore"),
    ("shoe", "Clean"),
    ("sneaker", "Clean"),
    ("handbag", "Clean & restore"),
    ("leather", "Clean & restore"),
    ("suede", "Clean & restore"),
    ("carpet", "Deep clean"),
    ("rug", "Deep clean"),
    ("curtain", "Deep clean"),
    ("drape", "Deep clean"),
    ("duvet", "Clean"),
    ("blanket", "Clean"),
    ("bedding", "Clean"),
)

# Alteration / adjustment fields a line item may carry (grounded, structured).
_INSTRUCTION_KEYS = ("instruction", "alteration", "adjustment", "work_instruction", "note")


def _int_or_none(value) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return int(f) if f == int(f) else None


def _item_service_text(item: dict, order_service: str) -> str:
    parts = [
        str(item.get(k, "")) for k in
        ("service", "service_code", "service_name", "service_display", "pricing_type")
    ]
    parts.append(str(order_service or ""))
    return " ".join(parts).lower()


def work_verb(item: dict, order_service: str) -> str:
    """The grounded work verb for one item, derived from its service signals.

    Falls back to the order's service display label (title-cased) when no known
    signal matches — so the line still reflects real data, never a guessed action.
    """
    text = _item_service_text(item, order_service)
    for signal, verb in _VERB_SIGNALS:
        if signal in text:
            return verb
    label = (order_service or "").strip()
    return label if label else "Process"


def _qty_name(qty: int | None, name: str) -> str:
    name = (name or "Item").strip()
    if qty is None or qty <= 1:
        return name if qty is None else f"{qty} {name}"
    # Light, safe pluralisation: only when whole-count > 1 and not already plural.
    display = name if name.lower().endswith("s") else f"{name}s"
    return f"{qty} {display}"


def _items(order: dict) -> list[dict]:
    line_items = order.get("line_items")
    if isinstance(line_items, list) and line_items:
        return [li for li in line_items if isinstance(li, dict)] or []
    items = order.get("items") or []
    if isinstance(items, str):
        items = [items]
    out: list[dict] = []
    for it in items:
        out.append(it if isinstance(it, dict) else {"name": str(it)})
    return out


def build_required_work(order: dict, active_notes: list[dict] | None = None) -> list[str]:
    """Concise, ordered list of what the facility must do for this order.

    Order: one line per confirmed line item (verb + quantity + name, plus any
    grounded alteration/adjustment instruction on that item), then any inspection
    requirements from confirmed notes. Returns ``[]`` when there is nothing
    structured to act on (the card then shows a neutral state).
    """
    service = order.get("service_display_name") or order.get("service_name_snapshot") or order.get("service") or ""
    lines: list[str] = []

    for item in _items(order):
        name = item.get("name") or item.get("canonical_name") or item.get("item") or item.get("item_code") or "Item"
        qty = _int_or_none(item.get("quantity"))
        verb = work_verb(item, service)
        base = f"{verb} {_qty_name(qty, str(name))}".strip()
        # Grounded per-item instruction (e.g. "Reduce length by 4 cm"), if present.
        instruction = ""
        for key in _INSTRUCTION_KEYS:
            val = item.get(key)
            if val and str(val).strip():
                instruction = str(val).strip()
                break
        lines.append(f"{base} — {instruction}" if instruction else base)

    # Inspection requirements are real, confirmed work items too.
    for note in (active_notes or []):
        if str(note.get("category", "")).upper() != "INSPECTION_REQUIREMENT":
            continue
        if str(note.get("status", "ACTIVE")).upper() != "ACTIVE":
            continue
        text = str(note.get("text", "")).strip()
        if not text:
            continue
        low = text.lower()
        lines.append(text if low.startswith(("inspect", "check", "verify")) else f"Inspect: {text}")

    # De-duplicate while preserving order (repeated identical items collapse).
    seen: set[str] = set()
    deduped: list[str] = []
    for ln in lines:
        key = ln.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(ln)
    return deduped
