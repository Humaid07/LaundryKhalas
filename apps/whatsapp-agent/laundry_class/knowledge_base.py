"""File-based knowledge base loader, section index, price parser and dummy-order
lookup for the Laundry Class agent.

The markdown file is the single source of truth. Prices are parsed directly from
the markdown pricing tables (not duplicated in code) so editing the `.md` is the
only place a price ever changes. Retrieval returns whole logical sections (split
on `## ` headings) so a pricing table is never cut in the middle of a row.

Loaded once at import time; restart the app (or call `reload()`) to pick up edits
— acceptable for the file-based testing phase per the task spec.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_KB_DIR = Path(__file__).resolve().parent.parent / "knowledge_base"
_KB_MD = _KB_DIR / "laundry_class_knowledge_base.md"
_ORDERS_JSON = _KB_DIR / "dummy_orders.json"


# ---------------------------------------------------------------------------
# Price rows
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PriceEntry:
    item: str
    service: str
    price_aed: float
    unit: str  # "per piece" | "per kg" | "per bag" | "per pair" | "inspection"
    notes: str

    @property
    def inspection_required(self) -> bool:
        return self.unit == "inspection"


# Item synonyms -> canonical item label as written in the markdown tables.
# Keeps lookup robust to how a customer phrases an item (t-shirt vs shirt,
# suit vs two-piece suit) without inventing anything not in the table.
_ITEM_SYNONYMS = {
    "t-shirt": "shirt",
    "t shirt": "shirt",
    "tshirt": "shirt",
    "shirts": "shirt",
    "suit": "two-piece suit",
    "2 piece suit": "two-piece suit",
    "2-piece suit": "two-piece suit",
    "two piece suit": "two-piece suit",
    "3 piece suit": "three-piece suit",
    "3-piece suit": "three-piece suit",
    "three piece suit": "three-piece suit",
    "trouser": "trousers",
    "pant": "trousers",
    "pants": "trousers",
    "blazer": "jacket or blazer",
    "jacket": "jacket or blazer",
    "gown": "evening dress",
    "wedding gown": "wedding dress",
    "abayas": "abaya",
    "kandura": "kandura or dishdasha",
    "dishdasha": "kandura or dishdasha",
    "sneakers": "sports shoes",
}


def _singularize(token: str) -> str:
    token = token.strip().lower()
    if token in _ITEM_SYNONYMS:
        return _ITEM_SYNONYMS[token]
    if token.endswith("ies"):
        return token[:-3] + "y"
    if token.endswith("es") and token[:-2] in _ITEM_LABELS:
        return token[:-2]
    if token.endswith("s") and token[:-1] in _ITEM_LABELS:
        return token[:-1]
    return token


# ---------------------------------------------------------------------------
# Markdown parsing
# ---------------------------------------------------------------------------
def _read_md() -> str:
    return _KB_MD.read_text(encoding="utf-8")


def _split_sections(md: str) -> dict[str, str]:
    """Split on `## ` headings into {title: section_text}. The section text
    includes its heading so a retrieved chunk is self-describing."""
    sections: dict[str, str] = {}
    current = "Overview"
    buf: list[str] = []
    for line in md.splitlines():
        if line.startswith("## "):
            if buf:
                sections[current] = "\n".join(buf).strip()
            current = line[3:].strip()
            buf = [line]
        else:
            buf.append(line)
    if buf:
        sections[current] = "\n".join(buf).strip()
    return sections


_TABLE_ROW = re.compile(r"^\|(.+)\|\s*$")


def _parse_price_tables(md: str) -> list[PriceEntry]:
    """Parse every `Pricing — ...` table row into a PriceEntry. Tables use the
    header: | Item | Service | Price (AED) | Unit | Notes |"""
    entries: list[PriceEntry] = []
    in_pricing = False
    header_seen = False
    for line in md.splitlines():
        if line.startswith("## "):
            in_pricing = line.startswith("## Pricing")
            header_seen = False
            continue
        if not in_pricing:
            continue
        m = _TABLE_ROW.match(line.strip())
        if not m:
            continue
        cells = [c.strip() for c in m.group(1).split("|")]
        if len(cells) < 4:
            continue
        if not header_seen:
            # first table row is the header, second is the |---| separator
            header_seen = True
            continue
        if set(cells[0]) <= {"-", ":", " "}:
            continue  # separator row
        item, service, price_raw, unit = cells[0], cells[1], cells[2], cells[3]
        notes = cells[4] if len(cells) > 4 else ""
        try:
            price = float(price_raw)
        except ValueError:
            continue
        entries.append(
            PriceEntry(
                item=item.strip(),
                service=service.strip(),
                price_aed=price,
                unit=unit.strip().lower(),
                notes=notes.strip(),
            )
        )
    return entries


# ---------------------------------------------------------------------------
# Cached load
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def _kb() -> dict:
    md = _read_md()
    sections = _split_sections(md)
    prices = _parse_price_tables(md)
    return {"md": md, "sections": sections, "prices": prices}


@lru_cache(maxsize=1)
def _orders() -> list[dict]:
    return json.loads(_ORDERS_JSON.read_text(encoding="utf-8"))


# Set of all canonical item labels, for singularization above.
_ITEM_LABELS: set[str] = set()


def reload() -> None:
    """Drop caches so the next access re-reads the files (used by restart tests)."""
    _kb.cache_clear()
    _orders.cache_clear()
    _build_item_labels()


def _build_item_labels() -> None:
    global _ITEM_LABELS
    _ITEM_LABELS = {e.item.lower() for e in _kb()["prices"]}


# ---------------------------------------------------------------------------
# Public API — sections / retrieval
# ---------------------------------------------------------------------------
def full_text() -> str:
    return _kb()["md"]


def sections() -> dict[str, str]:
    return _kb()["sections"]


# Intent -> ordered list of section-title keywords to retrieve.
_INTENT_SECTIONS = {
    "price_enquiry": ["Pricing"],
    "service_enquiry": ["Pricing", "Company Details"],
    "special_item_enquiry": ["Special", "Pricing"],
    "pickup_delivery_enquiry": ["Pickup and Delivery"],
    "new_order": ["Order Creation", "Pricing", "Pickup and Delivery"],
    "order_status": ["Turnaround", "Order Creation"],
    "delivery_reschedule": ["Pickup and Delivery", "Turnaround"],
    "cancellation": ["Cancellation"],
    "refund_request": ["Refund"],
    "damage_complaint": ["Damage or Lost-Item", "Stain-Removal"],
    "missing_item_complaint": ["Damage or Lost-Item"],
    "payment_question": ["Payment", "Company Details"],
    "greeting": ["Company Details"],
    "human_support": ["Company Details"],
}


def retrieve(intent: str, query: str = "") -> tuple[str, str]:
    """Return (section_title, section_text) most relevant to the intent.
    A light keyword fallback covers intents with no explicit mapping. Never
    returns the whole file — only one logical section, so the customer is
    never shown the raw KB dump."""
    secs = sections()
    wanted = _INTENT_SECTIONS.get(intent, [])
    for key in wanted:
        for title, text in secs.items():
            if key.lower() in title.lower():
                return title, text
    # keyword fallback against the query
    q = query.lower()
    for title, text in secs.items():
        if any(word in title.lower() for word in q.split() if len(word) > 3):
            return title, text
    return "Company Details", secs.get("Company Details", "")


# ---------------------------------------------------------------------------
# Public API — pricing (never invents)
# ---------------------------------------------------------------------------
def all_prices() -> list[PriceEntry]:
    return list(_kb()["prices"])


def find_price(item_text: str, service: str | None = None) -> PriceEntry | None:
    """Best price entry for an item phrase, optionally constrained to a service
    (e.g. "dry cleaning"). Returns None when the item is not in the table — the
    caller must then refuse to quote a price rather than invent one."""
    if not item_text:
        return None
    if not _ITEM_LABELS:
        _build_item_labels()
    token = _singularize(item_text)
    prices = _kb()["prices"]

    def matches_service(e: PriceEntry) -> bool:
        return service is None or service.lower() in e.service.lower()

    # exact canonical match first
    exact = [e for e in prices if e.item.lower() == token and matches_service(e)]
    if exact:
        return _cheapest_real(exact)
    # substring match (e.g. "silk dress" -> "dress")
    partial = [
        e for e in prices
        if (token in e.item.lower() or e.item.lower() in token) and matches_service(e)
    ]
    if partial:
        return _cheapest_real(partial)
    # if a service was requested but nothing matched, retry ignoring service
    if service is not None:
        return find_price(item_text, service=None)
    return None


def _cheapest_real(entries: list[PriceEntry]) -> PriceEntry:
    """Prefer a real (priced) entry over an inspection-only one; among priced
    entries, pick the lowest as the headline price."""
    priced = [e for e in entries if not e.inspection_required]
    if priced:
        return min(priced, key=lambda e: e.price_aed)
    return entries[0]


# ---------------------------------------------------------------------------
# Public API — dummy orders
# ---------------------------------------------------------------------------
def _digits(phone: str | None) -> str:
    return re.sub(r"\D", "", phone or "")


def find_order_by_phone(phone: str) -> dict | None:
    wanted = _digits(phone)
    if not wanted:
        return None
    for order in _orders():
        if _digits(order.get("phone_number")) == wanted:
            return order
    return None


def find_order_by_id(order_id: str) -> dict | None:
    wanted = re.sub(r"\s+", "", (order_id or "").upper())
    if not wanted:
        return None
    for order in _orders():
        if order.get("order_id", "").upper() == wanted:
            return order
    # tolerate trailing-number match (e.g. "1003" -> LC-TEST-1003)
    if wanted.isdigit():
        for order in _orders():
            if order.get("order_id", "").upper().endswith(wanted):
                return order
    return None


def all_orders() -> list[dict]:
    return list(_orders())


_build_item_labels()
