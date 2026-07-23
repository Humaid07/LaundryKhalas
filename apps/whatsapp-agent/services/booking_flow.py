"""Deterministic WhatsApp laundry-pickup BOOKING STATE MACHINE.

This is the source of truth for the booking flow. It is a PURE module: given the
current persisted booking + the inbound message, it returns the next state, the
exact field updates to persist, and the reply (text + optional interactive
list/buttons). It never calls an LLM and never invents a value — every stored
value is one the customer explicitly selected or typed, validated here.

Design contract (CLAUDE.md §5, task spec §§1/13/14):
  * The DB is the source of truth for the current step; the LLM may NOT skip a
    state. This module decides every transition deterministically.
  * Slots come from the DB (`available_slots` is injected so this stays pure and
    unit-testable — the webhook passes ``slots_repo.available_slots``).
  * Nothing is confirmed until the customer explicitly taps "Confirm booking" on
    the final summary. ``confirm_now`` is only ever True from
    ``waiting_for_confirmation`` + an explicit confirm.

The webhook is the thin persistence layer: it loads the open draft into a
``Booking``, calls :func:`advance` (or :func:`begin`), persists ``reply.updates``
+ ``reply.state``, and renders ``reply.interactive`` (list/buttons) with a
numbered-text fallback.
"""
from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass, field

from agents.whatsapp_agent import tools
from rules import pickup_instructions
from services import catalogue, pricing
from services.order_extraction import area_to_city

# --- States -----------------------------------------------------------------
# Step 1 = category ("service"); step 2 = sub-category (only for big categories);
# step 3 = item + quantity/measure; then "add another / done". After the items
# are collected the flow continues to the SAME proven name→date→…→confirm path.
WAITING_FOR_SERVICE = "waiting_for_service"             # category selection
WAITING_FOR_SUBCATEGORY = "waiting_for_subcategory"     # sub-category (Everyday Wear, …)
WAITING_FOR_ITEM = "waiting_for_item"                   # item within the (sub)category
WAITING_FOR_ITEM_QUANTITY = "waiting_for_item_quantity"  # how many of the item
WAITING_FOR_MEASURE = "waiting_for_item_measure"        # sqm for per-sqm items
WAITING_FOR_MORE_ITEMS = "waiting_for_more_items"       # add another item / done
WAITING_FOR_NAME = "waiting_for_customer_name"          # free-text name entry
WAITING_FOR_NAME_CONFIRM = "waiting_for_name_confirm"   # confirm a profile/verified name
WAITING_FOR_PICKUP_DATE = "waiting_for_pickup_date"
WAITING_FOR_PICKUP_SLOT = "waiting_for_pickup_slot"
WAITING_FOR_ADDRESS = "waiting_for_address"
WAITING_FOR_PICKUP_INSTRUCTIONS = "waiting_for_pickup_instructions"
WAITING_FOR_INSTRUCTION_TEXT = "waiting_for_instruction_text"
WAITING_FOR_CONFIRMATION = "waiting_for_confirmation"
WAITING_FOR_CHANGE_FIELD = "waiting_for_change_field"
# --- Targeted single-field edit states (spec: ORDER_EDIT_VALUE) --------------
# Reached from WAITING_FOR_CHANGE_FIELD after the customer picks ONE field. Each
# asks only for that field and returns straight to WAITING_FOR_CONFIRMATION with
# a PATCH of just that field — it never resumes linear collection. The specific
# EDITING_* state IS the persisted "editing_field", so it survives restarts and
# stays isolated per conversation (per phone number).
EDITING_NAME = "editing_name"
EDITING_SERVICE = "editing_service"
EDITING_DATE = "editing_date"
EDITING_SLOT = "editing_slot"
EDITING_ADDRESS = "editing_address"
EDITING_INSTRUCTIONS = "editing_instructions"
EDITING_INSTRUCTION_TEXT = "editing_instruction_text"
# Active-draft protection: the customer sent a new-order intent while a draft is
# in progress; we ask continue / start-new / cancel.
RESUME_OR_NEW = "resume_or_new"
BOOKING_CONFIRMED = "booking_confirmed"
BOOKING_CANCELLED = "booking_cancelled"
# Set on a CONFIRMED order after its confirmation message, so the conversation
# can offer next actions (place another order / check status / support). It is a
# conversation-level marker, NOT an active draft — a completed workflow never
# blocks a new one (spec §"state-model changes").
POST_ORDER = "post_order"

# Stable next-action ids shown after an order is confirmed (spec §"required
# behaviour after order confirmation").
NEW_ORDER = "NEW_ORDER"
CHECK_ORDER_STATUS = "CHECK_ORDER_STATUS"
HUMAN_SUPPORT = "HUMAN_SUPPORT"

_EDITING_STATES = frozenset({
    EDITING_NAME, EDITING_SERVICE, EDITING_DATE, EDITING_SLOT, EDITING_ADDRESS,
    EDITING_INSTRUCTIONS, EDITING_INSTRUCTION_TEXT,
})

ACTIVE_STATES = frozenset({
    WAITING_FOR_SERVICE, WAITING_FOR_SUBCATEGORY, WAITING_FOR_ITEM,
    WAITING_FOR_ITEM_QUANTITY, WAITING_FOR_MEASURE, WAITING_FOR_MORE_ITEMS,
    WAITING_FOR_NAME, WAITING_FOR_NAME_CONFIRM,
    WAITING_FOR_PICKUP_DATE, WAITING_FOR_PICKUP_SLOT,
    WAITING_FOR_ADDRESS, WAITING_FOR_PICKUP_INSTRUCTIONS, WAITING_FOR_INSTRUCTION_TEXT,
    WAITING_FOR_CONFIRMATION, WAITING_FOR_CHANGE_FIELD, RESUME_OR_NEW,
}) | _EDITING_STATES
TERMINAL_STATES = frozenset({BOOKING_CONFIRMED, BOOKING_CANCELLED})

# Dubai has no DST — a fixed +04:00 keeps pickup_start/end_time correct without a
# tz database and keeps this module (and its tests) deterministic.
_GST = _dt.timezone(_dt.timedelta(hours=4))


# --- Interactive reply model ------------------------------------------------
@dataclass
class Option:
    id: str                       # stable selection id, e.g. "service:boutique_clean_press"
    title: str
    description: str | None = None


@dataclass
class Interactive:
    kind: str                     # "list" | "buttons"
    body: str
    options: list[Option]
    button_text: str | None = None   # list only ("Choose a service")
    header: str | None = None
    section_title: str | None = None


@dataclass
class BookingReply:
    text: str                     # message body (also the interactive body / fallback intro)
    state: str                    # conversation_state to persist
    updates: dict = field(default_factory=dict)   # order-row fields to persist (data only)
    interactive: Interactive | None = None
    confirm_now: bool = False     # flip the draft to a confirmed operational order (once)
    cancel_now: bool = False      # mark the draft cancelled
    start_new_order: bool = False # abandon this draft + start a fresh workflow (webhook acts)
    log_event: str | None = None  # structured-log hint for the webhook


@dataclass
class Booking:
    """The subset of the open draft-order row the FSM reasons over."""
    conversation_state: str | None = None
    customer_name: str | None = None        # CONFIRMED booking name (persisted snapshot)
    service_id: str | None = None                # = catalogue category code
    service_name_snapshot: str | None = None     # = catalogue category name
    line_items: list | None = None               # completed priced order lines (snapshot)
    browse_service_code: str | None = None        # sub-category whose items are shown
    pending_item_code: str | None = None          # item awaiting a quantity/measure
    pickup_date: _dt.date | None = None
    pickup_slot_id: str | None = None
    pickup_slot_label: str | None = None
    pickup_address: str | None = None
    pickup_area: str | None = None
    pickup_instruction_code: str | None = None
    pickup_instruction_text: str | None = None
    # --- transient context (NOT persisted; supplied by the webhook per message) --
    # The unverified WhatsApp push/profile name — only ever offered for the
    # customer to confirm, never saved as the booking name automatically.
    whatsapp_profile_name: str | None = None
    # A previously CONFIRMED name for this customer (from an earlier order), which
    # may be reused after the customer agrees.
    verified_name: str | None = None


@dataclass
class Inbound:
    """Normalized inbound message the FSM consumes."""
    text: str = ""
    selection_id: str | None = None      # list row id / button id (e.g. "service:...")
    latitude: float | None = None
    longitude: float | None = None

    @property
    def is_location(self) -> bool:
        return self.latitude is not None and self.longitude is not None


# --- Intent detection (deterministic) ---------------------------------------
_BOOK_INTENT = re.compile(
    r"\b(book|schedule|arrange|request|set\s?up|need|want)\b[\w\s,]*?"
    r"\b(pick\s?up|pick-?up|collection|collect|laundry|wash|clean(?:ing)?|dry\s?clean|service)\b"
    r"|\bpick\s?up\b|\bpickup\b|\bbook(?:ing)?\b",
    re.IGNORECASE,
)
_CANCEL_WORDS = re.compile(r"\b(cancel|stop|nevermind|never mind|forget it)\b", re.IGNORECASE)

# A NEW/second order (vs. continuing the current one). Covers "another order",
# "new order", "place another", "book another", "one more", "also need X", and
# explicit restarts ("start over", "restart").
_NEW_ORDER_INTENT = re.compile(
    r"\b(another|new|second|one\s?more|also)\b[\w\s]*?"
    r"\b(order|pick\s?up|pick-?up|booking|laundry|service|clean(?:ing)?|wash)\b"
    r"|\bplace\s+another\b|\bbook\s+another\b|\bstart\s+over\b|\brestart\b",
    re.IGNORECASE,
)
_STATUS_INTENT = re.compile(
    r"\b(order\s+status|status\s+of|track\s+my|where('?s|\s+is)\s+my\s+order|my\s+order\s+status)\b",
    re.IGNORECASE,
)


def is_book_pickup_intent(text: str) -> bool:
    """True when a free-text message expresses intent to book a pickup. Used only
    to START a booking — it never selects a service (that is a separate step)."""
    return bool(_BOOK_INTENT.search(text or ""))


def is_new_order_intent(text: str) -> bool:
    """True when the customer clearly wants ANOTHER/new order (not to continue the
    current step). Used to allow a second order after one is confirmed, and to
    trigger continue/start-new protection when a draft is still in progress."""
    return bool(_NEW_ORDER_INTENT.search(text or ""))


def is_status_intent(text: str) -> bool:
    return bool(_STATUS_INTENT.search(text or ""))


def has_progress(b: "Booking") -> bool:
    """True if the draft already has at least one collected field — used to decide
    whether a mid-draft new-order intent needs the continue/start-new prompt."""
    return any([b.customer_name, b.service_id, b.pickup_date, b.pickup_slot_id,
                b.pickup_address, b.pickup_instruction_code])


# --- Customer name -----------------------------------------------------------
# Explicit self-introductions we trust to extract a name FROM A LONGER MESSAGE
# (e.g. "I need dry cleaning tomorrow. I'm Fatima and pickup is from JVC.").
_NAME_INTRO = re.compile(
    r"(?:my\s+name\s+is|i\s*'?\s*am|i'?m|this\s+is|it'?s|name\s*[:\-]|"
    r"book\s+it\s+under|book\s+under|under\s+the\s+name|under)\s+"
    r"([A-Za-z][A-Za-z .'\-]{0,38}?)"
    r"(?=[.,;!?]|\s+and\b|\s+pickup\b|\s+i\s+need\b|\s+for\b|$)",
    re.IGNORECASE,
)
# A bare name typed on its own at the name step (letters, spaces, ' and -).
_NAME_TOKEN = re.compile(r"^[A-Za-z][A-Za-z .'\-]{0,38}$")
_NAME_STOPWORDS = {
    "yes", "no", "ok", "okay", "hi", "hello", "hey", "thanks", "thank you",
    "confirm", "cancel", "change", "today", "tomorrow", "none", "new", "continue",
}


def validate_name(raw: str | None) -> str | None:
    """Return a cleaned, valid customer name or None. Accepts common international
    names (Sara, Amaan Patel, Mary Jane, Abdul-Rahman, O'Connor); rejects blanks,
    pure numbers/punctuation, obvious command words, and absurdly long strings.
    Does NOT force first+last or Western formatting."""
    if not raw:
        return None
    name = re.sub(r"\s+", " ", raw).strip(" .,-")
    if not name or len(name) > 40:
        return None
    if name.lower() in _NAME_STOPWORDS:
        return None
    if not re.search(r"[A-Za-z]", name):        # must contain a letter
        return None
    if re.fullmatch(r"[\d\W_]+", name):          # only digits/punctuation
        return None
    return name


def extract_name(text: str | None) -> str | None:
    """Pull a name out of an explicit self-introduction, else None. Never guesses
    from a bare word (that is handled only when we are explicitly asking)."""
    if not text:
        return None
    m = _NAME_INTRO.search(text)
    return validate_name(m.group(1)) if m else None


# --- Service catalogue helpers (step 1 = the 9 real price-list categories) ---
def _service_options() -> list[Option]:
    """The WhatsApp step-1 list: the real price-list categories (Clean & Press,
    Press Only, …). The row id is ``service:<CATEGORY_CODE>``."""
    return [
        Option(id=f"service:{c['code']}", title=c["name"],
               description=_clip(c.get("description")))
        for c in catalogue.categories()
    ]


def _clip(text: str | None) -> str | None:
    if not text:
        return None
    text = text.strip()
    return (text[:69] + "…") if len(text) > 70 else (text or None)


def resolve_service(inbound: Inbound) -> tuple[str | None, str]:
    """Return (category_code, reason). reason: 'ok' | 'ambiguous' | 'invalid'.
    Free text resolves via category aliases, then via an item alias (mapping the
    item back to its category). Bare 'iron/press' is deliberately ambiguous so
    the agent asks Clean & Press vs Press Only (task spec §7/§20)."""
    ids = {c["code"] for c in catalogue.categories()}
    sel = inbound.selection_id or ""
    if sel.startswith("service:"):
        key = sel.split(":", 1)[1]
        return (key, "ok") if key in ids else (None, "invalid")

    text = (inbound.text or "").strip()
    if text.isdigit():
        idx = int(text) - 1
        opts = _service_options()
        if 0 <= idx < len(opts):
            return (opts[idx].id.split(":", 1)[1], "ok")
        return (None, "invalid")

    if catalogue.is_ambiguous_iron(text):
        return (None, "ambiguous")
    code = catalogue.resolve_category_alias(text)
    if code:
        return (code, "ok")
    item_codes, reason = catalogue.resolve_item_alias(text)
    if reason == "ok":
        item = catalogue.item_by_code(item_codes[0])
        return (item["category_code"], "ok") if item else (None, "invalid")
    if reason == "ambiguous":
        return (None, "ambiguous")
    return (None, "invalid")


# --- Item catalogue helpers (steps 2-3) -------------------------------------
def _subcategory_options(category_code: str) -> list[Option]:
    return [
        Option(id=f"sub:{s['code']}", title=s["name"])
        for s in catalogue.services_for_category(category_code)
    ]


def _item_options(service_code: str) -> list[Option]:
    opts: list[Option] = []
    for it in catalogue.items_for_service(service_code):
        opts.append(Option(
            id=f"item:{it['item_code']}",
            title=it["canonical_name"],
            description=catalogue.item_price_label(it),
        ))
    return opts


def resolve_subcategory(inbound: Inbound, category_code: str) -> tuple[str | None, str]:
    svcs = catalogue.services_for_category(category_code)
    ids = {s["code"] for s in svcs}
    sel = inbound.selection_id or ""
    if sel.startswith("sub:"):
        code = sel.split(":", 1)[1]
        return (code, "ok") if code in ids else (None, "invalid")
    text = (inbound.text or "").strip()
    if text.isdigit():
        idx = int(text) - 1
        if 0 <= idx < len(svcs):
            return (svcs[idx]["code"], "ok")
        return (None, "invalid")
    low = text.lower()
    hits = [s["code"] for s in svcs if s["name"].lower() in low]
    if len(hits) == 1:
        return (hits[0], "ok")
    return (None, "invalid")


def resolve_item(inbound: Inbound, service_code: str | None,
                 category_code: str | None) -> tuple[str | None, str]:
    """Resolve an item within the currently-browsed (sub)category. Returns
    (item_code, reason): 'ok' | 'ambiguous' | 'invalid'."""
    items = (catalogue.items_for_service(service_code) if service_code
             else catalogue.items_for_category(category_code or ""))
    sel = inbound.selection_id or ""
    if sel.startswith("item:"):
        code = sel.split(":", 1)[1]
        # An item selection is valid even if it belongs to another sub-category of
        # the same category (the customer may have free-typed it).
        return (code, "ok") if catalogue.item_by_code(code) else (None, "invalid")
    text = (inbound.text or "").strip()
    if text.isdigit():
        idx = int(text) - 1
        if 0 <= idx < len(items):
            return (items[idx]["item_code"], "ok")
        return (None, "invalid")
    # free text -> alias within this category first, then the whole catalogue
    hit_codes, reason = catalogue.resolve_item_alias(text, category_code=category_code)
    if reason == "ok":
        return (hit_codes[0], "ok")
    if reason == "ambiguous":
        return (None, "ambiguous")
    hit_codes, reason = catalogue.resolve_item_alias(text)
    if reason == "ok":
        return (hit_codes[0], "ok")
    return (None, reason if reason == "ambiguous" else "invalid")


def _raw_lines(booking: "Booking") -> list[dict]:
    """The completed order lines as {item_code, quantity, measure} (for repricing)."""
    out: list[dict] = []
    for ln in booking.line_items or []:
        out.append({
            "item_code": ln.get("item_code"),
            "quantity": ln.get("quantity", 1),
            "measure": ln.get("measure"),
        })
    return out


def _pricing_updates(raw_lines: list[dict], category_code: str | None,
                     category_name: str | None) -> dict:
    """Recompute the quote from raw lines and return the order-row PATCH (priced
    line snapshot + VAT columns + amount mirror)."""
    q = pricing.calculate_estimate(raw_lines)
    d = q.to_dict()
    return {
        "line_items": d["lines"],
        "catalogue_category_code": category_code,
        "catalogue_category_name": category_name,
        "subtotal_amount": q.subtotal_excluding_vat,
        "vat_rate": q.vat_rate,
        "vat_amount": q.vat_amount,
        "estimated_total": q.estimated_total_including_vat,
        "amount": q.estimated_total_including_vat,
        "pricing_is_estimated": q.is_estimated,
    }


def _quote_for(booking: "Booking"):
    return pricing.calculate_estimate(_raw_lines(booking))


_QTY_WORDS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4,
              "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
              "single": 1, "couple": 2, "pair": 1, "dozen": 12}


def _extract_leading_qty(text: str | None) -> int | None:
    """A quantity stated alongside the item ('3 shirts', 'two ties'), else None."""
    if not text:
        return None
    m = re.match(r"\s*(\d{1,3})\b", text)
    if m:
        n = int(m.group(1))
        return n if 1 <= n <= 500 else None
    first = text.strip().split()[0].lower() if text.strip() else ""
    return _QTY_WORDS.get(first)


def _parse_qty(text: str | None) -> int | None:
    if not text:
        return None
    m = re.search(r"(\d{1,3})", text)
    if m:
        n = int(m.group(1))
        return n if 1 <= n <= 500 else None
    for word, n in _QTY_WORDS.items():
        if re.search(rf"\b{word}\b", text.lower()):
            return n
    return None


def _parse_measure(text: str | None) -> float | None:
    if not text:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)", text)
    if not m:
        return None
    v = float(m.group(1))
    return v if 0 < v <= 1000 else None


# --- Item-flow prompt builders ----------------------------------------------
def _subcategory_prompt(category_code: str) -> BookingReply:
    cat = catalogue.category_by_code(category_code) or {}
    body = f"Great — {cat.get('name', 'that service')}. Which type of item?"
    return BookingReply(
        text=body, state=WAITING_FOR_SUBCATEGORY,
        interactive=Interactive(
            kind="list", body=body, button_text="Choose a type",
            section_title=cat.get("name") or "Types",
            options=_subcategory_options(category_code)),
        log_event="subcategory_list_sent")


def _item_prompt(category_code: str, service_code: str | None) -> BookingReply:
    svc = next((s for s in catalogue.services_for_category(category_code)
                if s["code"] == service_code), None)
    section = (svc or {}).get("name") or (catalogue.category_by_code(category_code) or {}).get("name") or "Items"
    body = "Which item would you like? You can also tell me the quantity (e.g. '3 shirts')."
    options = _item_options(service_code) if service_code else [
        Option(id=f"item:{i['item_code']}", title=i["canonical_name"],
               description=catalogue.item_price_label(i))
        for i in catalogue.items_for_category(category_code)]
    return BookingReply(
        text=body, state=WAITING_FOR_ITEM,
        interactive=Interactive(
            kind="list", body=body, button_text="Choose an item",
            section_title=section, options=options),
        updates={"browse_service_code": service_code},
        log_event="item_list_sent")


def _quantity_prompt(item: dict) -> BookingReply:
    body = f"How many {item['canonical_name']}? ({catalogue.item_price_label(item)})"
    return BookingReply(text=body, state=WAITING_FOR_ITEM_QUANTITY,
                        log_event="quantity_requested")


def _measure_prompt(item: dict) -> BookingReply:
    body = (f"Roughly how many square metres of {item['canonical_name']}? "
            f"({catalogue.item_price_label(item)} — estimated; the team confirms "
            "the final measurement at pickup.)")
    return BookingReply(text=body, state=WAITING_FOR_MEASURE,
                        log_event="measure_requested")


def _more_items_prompt(last_item_code: str | None, quantity) -> BookingReply:
    item = catalogue.item_by_code(last_item_code) if last_item_code else None
    added = (f"Added {_fmt_num(quantity)} × {item['canonical_name']}. "
             if item else "")
    body = f"{added}Would you like to add another item, or continue with your order?"
    return BookingReply(
        text=body, state=WAITING_FOR_MORE_ITEMS,
        interactive=Interactive(kind="buttons", body=body, options=[
            Option(id="add_item", title="Add another item"),
            Option(id="items_done", title="That's all")]),
        log_event="more_items_prompt")


def _fmt_num(v) -> str:
    try:
        f = float(v)
        return str(int(f)) if f == int(f) else f"{f:g}"
    except (TypeError, ValueError):
        return str(v)


def _iron_disambiguation_prompt() -> BookingReply:
    body = ("Would you like Clean & Press (we wash and iron) or Press Only "
            "(iron an item that's already washed)?")
    return BookingReply(
        text=body, state=WAITING_FOR_SERVICE,
        interactive=Interactive(kind="buttons", body=body, options=[
            Option(id="service:CLEAN_PRESS", title="Clean & Press"),
            Option(id="service:PRESS_ONLY", title="Press Only")]),
        log_event="iron_disambiguation")


def _resume_item_collection(booking: "Booking") -> BookingReply:
    """Re-issue the correct item-collection prompt for a draft mid-collection."""
    if booking.pending_item_code:
        item = catalogue.item_by_code(booking.pending_item_code)
        if item and item["pricing_type"] == "PER_SQM":
            return _measure_prompt(item)
        if item:
            return _quantity_prompt(item)
    subs = catalogue.services_for_category(booking.service_id or "")
    if len(subs) > 1 and not booking.browse_service_code:
        return _subcategory_prompt(booking.service_id)
    code = booking.browse_service_code or (subs[0]["code"] if subs else None)
    return _item_prompt(booking.service_id, code)


# --- Item-flow value handlers -----------------------------------------------
def _enter_category(booking: "Booking", category_code: str) -> BookingReply:
    cat = catalogue.category_by_code(category_code) or {}
    name = cat.get("name") or category_code
    manual = cat.get("default_pricing_type") in ("STARTING_FROM", "INSPECTION_REQUIRED")
    base_updates = {
        "service_id": category_code,
        "service": name,
        "service_display_name": name,
        "service_name_snapshot": name,
        "catalogue_category_code": category_code,
        "catalogue_category_name": name,
        "unit_type": (cat.get("default_pricing_unit") or "ITEM").lower(),
        "requires_manual_quote": bool(manual),
        "_touch_service_selected_at": True,
    }
    subs = catalogue.services_for_category(category_code)
    if len(subs) > 1:
        reply = _subcategory_prompt(category_code)
    else:
        code = subs[0]["code"] if subs else None
        reply = _item_prompt(category_code, code)
    reply.updates = {**base_updates, **(reply.updates or {})}
    reply.log_event = "service_selected"
    return reply


def _on_subcategory(booking: "Booking", inbound: Inbound) -> BookingReply:
    code, reason = resolve_subcategory(inbound, booking.service_id or "")
    if reason != "ok" or not code:
        r = _subcategory_prompt(booking.service_id)
        r.text = "Please choose one of the item types below:"
        if r.interactive:
            r.interactive.body = r.text
        r.log_event = "subcategory_invalid"
        return r
    reply = _item_prompt(booking.service_id, code)
    reply.updates = {**(reply.updates or {}), "browse_service_code": code}
    return reply


def _start_item(booking: "Booking", item_code: str, inbound: Inbound) -> BookingReply:
    """An item was chosen: ask sqm for per-sqm items, use an inline quantity if
    the customer gave one, else ask the quantity."""
    item = catalogue.item_by_code(item_code)
    if not item:
        return _item_prompt(booking.service_id, booking.browse_service_code)
    if item["pricing_type"] == "PER_SQM":
        r = _measure_prompt(item)
        r.updates = {"pending_item_code": item_code}
        return r
    qty = _extract_leading_qty(inbound.text)
    if qty:
        return _complete_line(booking, item_code, qty, None)
    r = _quantity_prompt(item)
    r.updates = {"pending_item_code": item_code}
    return r


def _on_item(booking: "Booking", inbound: Inbound) -> BookingReply:
    item_code, reason = resolve_item(inbound, booking.browse_service_code, booking.service_id)
    if reason == "ambiguous":
        r = _item_prompt(booking.service_id, booking.browse_service_code)
        r.text = "More than one item matches that — please pick the exact one below:"
        if r.interactive:
            r.interactive.body = r.text
        r.log_event = "item_selection_ambiguous"
        return r
    if reason != "ok" or not item_code:
        r = _item_prompt(booking.service_id, booking.browse_service_code)
        r.text = "Sorry, I didn't catch a valid item. Please choose one below:"
        if r.interactive:
            r.interactive.body = r.text
        r.log_event = "item_selection_invalid"
        return r
    return _start_item(booking, item_code, inbound)


def _on_item_quantity(booking: "Booking", inbound: Inbound) -> BookingReply:
    qty = _parse_qty(inbound.text)
    if not qty:
        item = catalogue.item_by_code(booking.pending_item_code) or {}
        name = item.get("canonical_name", "the item")
        return BookingReply(
            text=f"Please tell me how many {name} you'd like (a number, e.g. 3).",
            state=WAITING_FOR_ITEM_QUANTITY, log_event="quantity_invalid")
    return _complete_line(booking, booking.pending_item_code, qty, None)


def _on_measure(booking: "Booking", inbound: Inbound) -> BookingReply:
    m = _parse_measure(inbound.text)
    if m is None:
        return BookingReply(
            text="Please share an approximate size in square metres (e.g. 6).",
            state=WAITING_FOR_MEASURE, log_event="measure_invalid")
    return _complete_line(booking, booking.pending_item_code, 1, m)


def _complete_line(booking: "Booking", item_code: str | None, quantity, measure) -> BookingReply:
    if not item_code or not catalogue.item_by_code(item_code):
        return _item_prompt(booking.service_id, booking.browse_service_code)
    raw = _raw_lines(booking) + [
        {"item_code": item_code, "quantity": quantity, "measure": measure}]
    updates = _pricing_updates(raw, booking.service_id, booking.service_name_snapshot)
    updates["pending_item_code"] = None
    reply = _more_items_prompt(item_code, quantity)
    reply.updates = {**updates, **(reply.updates or {})}
    reply.log_event = "item_added"
    return reply


async def _on_more_items(booking: "Booking", inbound: Inbound, available_slots) -> BookingReply:
    sel = inbound.selection_id or ""
    low = (inbound.text or "").strip().lower()
    if sel == "add_item" or low in ("add", "1", "another", "more", "add another item",
                                    "add another", "yes"):
        subs = catalogue.services_for_category(booking.service_id or "")
        if len(subs) > 1:
            return _subcategory_prompt(booking.service_id)
        code = booking.browse_service_code or (subs[0]["code"] if subs else None)
        return _item_prompt(booking.service_id, code)
    if sel == "items_done" or low in ("done", "2", "that's all", "thats all", "no",
                                      "continue", "that is all", "nothing", "finish",
                                      "no more", "all done"):
        return await _after_items(booking, available_slots)
    # The customer may have typed another item directly ("also 2 ties").
    item_code, reason = resolve_item(inbound, booking.browse_service_code, booking.service_id)
    if reason == "ok" and item_code:
        return _start_item(booking, item_code, inbound)
    return _more_items_prompt(None, None)


async def _after_items(booking: "Booking", available_slots) -> BookingReply:
    """Items are collected — continue to the SAME proven name→date→…→confirm flow."""
    if not booking.customer_name:
        return _name_prompt(booking)
    return await next_prompt_for(booking, available_slots)


# --- Date parsing (deterministic, never past) -------------------------------
_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m", "%d-%m",
                 "%d %B", "%d %b", "%B %d", "%b %d", "%d %B %Y", "%d %b %Y")


def parse_pickup_date(inbound: Inbound, today: _dt.date) -> tuple[_dt.date | None, str]:
    """Return (date, reason). reason: 'ok' | 'other' | 'past' | 'invalid'.
    'other' means the customer asked to type a custom date."""
    sel = inbound.selection_id or ""
    if sel == "date:today":
        return today, "ok"
    if sel == "date:tomorrow":
        return today + _dt.timedelta(days=1), "ok"
    if sel == "date:other":
        return None, "other"

    text = (inbound.text or "").strip().lower()
    if not text:
        return None, "invalid"
    if text in ("today", "tonight", "1"):        # "1" = numbered-fallback "Today"
        return today, "ok"
    if text in ("tomorrow", "2"):                 # "2" = numbered-fallback "Tomorrow"
        return today + _dt.timedelta(days=1), "ok"
    if text == "3":                               # "3" = numbered-fallback "Choose another date"
        return None, "other"

    raw = re.sub(r"(\d+)(st|nd|rd|th)\b", r"\1", inbound.text.strip(), flags=re.IGNORECASE)
    for fmt in _DATE_FORMATS:
        try:
            parsed = _dt.datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
        # formats without a year default to 1900 -> roll to the next occurrence
        if "%Y" not in fmt:
            parsed = parsed.replace(year=today.year)
            if parsed < today:
                parsed = parsed.replace(year=today.year + 1)
        if parsed < today:
            return None, "past"
        return parsed, "ok"
    return None, "invalid"


# --- Slot helpers -----------------------------------------------------------
def _slot_options(slots: list[dict]) -> list[Option]:
    return [Option(id=f"slot:{s['slot_id']}", title=s["label"]) for s in slots]


def resolve_slot(inbound: Inbound, slots: list[dict]) -> tuple[dict | None, str]:
    by_id = {s["slot_id"]: s for s in slots}
    sel = inbound.selection_id or ""
    if sel.startswith("slot:"):
        sid = sel.split(":", 1)[1]
        return (by_id[sid], "ok") if sid in by_id else (None, "invalid")
    text = (inbound.text or "").strip()
    if text.isdigit():
        idx = int(text) - 1
        if 0 <= idx < len(slots):
            return slots[idx], "ok"
    return None, "invalid"


# --- Instruction helpers ----------------------------------------------------
def _instruction_options() -> list[Option]:
    return [Option(id=f"instruction:{i['code']}", title=i["label"]) for i in pickup_instructions()]


def resolve_instruction(inbound: Inbound) -> tuple[dict | None, str]:
    by_code = {i["code"]: i for i in pickup_instructions()}
    sel = inbound.selection_id or ""
    if sel.startswith("instruction:"):
        code = sel.split(":", 1)[1]
        return (by_code[code], "ok") if code in by_code else (None, "invalid")
    text = (inbound.text or "").strip()
    opts = pickup_instructions()
    if text.isdigit():
        idx = int(text) - 1
        if 0 <= idx < len(opts):
            return opts[idx], "ok"
    # exact label match (fallback typed reply)
    for i in opts:
        if text.lower() == i["label"].lower():
            return i, "ok"
    return None, "invalid"


# --- Prompt builders --------------------------------------------------------
def _service_prompt() -> BookingReply:
    return BookingReply(
        text="Sure! Which laundry service would you like to book?",
        state=WAITING_FOR_SERVICE,
        interactive=Interactive(
            kind="list",
            body="Sure! Which laundry service would you like to book?",
            button_text="Choose a service",
            section_title="Our services",
            options=_service_options(),
        ),
        log_event="service_list_sent",
    )


def _date_prompt(service_label: str) -> BookingReply:
    return BookingReply(
        text=f"Great, you selected {service_label}. Which day would you like the pickup?",
        state=WAITING_FOR_PICKUP_DATE,
        interactive=Interactive(
            kind="buttons",
            body=f"Great, you selected {service_label}. Which day would you like the pickup?",
            options=[
                Option(id="date:today", title="Today"),
                Option(id="date:tomorrow", title="Tomorrow"),
                Option(id="date:other", title="Choose another date"),
            ],
        ),
    )


def _slot_prompt(slots: list[dict], date_label: str) -> BookingReply:
    if not slots:
        return BookingReply(
            text=(f"Sorry, we have no pickup slots available for {date_label}. "
                  "Please choose another day."),
            state=WAITING_FOR_PICKUP_DATE,
            interactive=Interactive(
                kind="buttons",
                body=f"No slots for {date_label}. Pick another day?",
                options=[
                    Option(id="date:today", title="Today"),
                    Option(id="date:tomorrow", title="Tomorrow"),
                    Option(id="date:other", title="Choose another date"),
                ],
            ),
            log_event="no_slots_available",
        )
    return BookingReply(
        text=f"Please choose a pickup time for {date_label}:",
        state=WAITING_FOR_PICKUP_SLOT,
        interactive=Interactive(
            kind="list",
            body=f"Please choose a pickup time for {date_label}:",
            button_text="Choose a time",
            section_title="Available pickup times",
            options=_slot_options(slots),
        ),
    )


def _address_prompt() -> BookingReply:
    return BookingReply(
        text="Please share your pickup address or WhatsApp location.",
        state=WAITING_FOR_ADDRESS,
    )


def _instructions_prompt() -> BookingReply:
    return BookingReply(
        text="Do you have any pickup instructions for our driver?",
        state=WAITING_FOR_PICKUP_INSTRUCTIONS,
        interactive=Interactive(
            kind="list",
            body="Do you have any pickup instructions for our driver?",
            button_text="Choose",
            section_title="Pickup instructions",
            options=_instruction_options(),
        ),
    )


def _format_date(d: _dt.date | None) -> str:
    return d.strftime("%A, %d %B") if d else "—"


def _summary_text(b: Booking, *, header: str = "Please confirm your pickup details:") -> str:
    instr = b.pickup_instruction_text or "No additional instructions"
    lines = [
        header, "",
        f"Name: {b.customer_name or 'Name pending'}",
        f"Service: {b.service_name_snapshot or '—'}",
    ]
    if b.line_items:
        lines += ["", pricing.format_quote_summary(_quote_for(b))]
    lines += [
        "",
        f"Pickup date: {_format_date(b.pickup_date)}",
        f"Pickup time: {b.pickup_slot_label or '—'}",
        f"Address: {b.pickup_address or '—'}",
        f"Instructions: {instr}",
        "",
        "Would you like to confirm this order?",
    ]
    return "\n".join(lines)


def _confirmation_prompt(b: Booking, *, header: str = "Please confirm your pickup details:") -> BookingReply:
    body = _summary_text(b, header=header)
    return BookingReply(
        text=body,
        state=WAITING_FOR_CONFIRMATION,
        interactive=Interactive(
            kind="buttons",
            body=body,
            options=[
                Option(id="confirm_booking", title="Confirm booking"),
                Option(id="change_details", title="Change details"),
                Option(id="cancel_booking", title="Cancel"),
            ],
        ),
        log_event="confirmation_requested",
    )


def _change_menu() -> BookingReply:
    return BookingReply(
        text="What would you like to change?",
        state=WAITING_FOR_CHANGE_FIELD,
        interactive=Interactive(
            kind="list",
            body="What would you like to change?",
            button_text="Choose",
            section_title="Change",
            options=[
                Option(id="change:name", title="Customer name"),
                Option(id="change:service", title="Service"),
                Option(id="change:date", title="Pickup date"),
                Option(id="change:slot", title="Pickup time"),
                Option(id="change:address", title="Address"),
                Option(id="change:instructions", title="Pickup instructions"),
            ],
        ),
    )


# --- Entry point ------------------------------------------------------------
def begin() -> BookingReply:
    """Start a fresh booking: go straight to service selection. No service, date,
    address, or anything else is assumed."""
    return _service_prompt()


def begin_new_order() -> BookingReply:
    """Start an ADDITIONAL order (the customer already has a confirmed one). Same
    service-selection step, but a wording that acknowledges it's another order."""
    r = _service_prompt()
    r.text = "Certainly. Let's create another order. Which service would you like?"
    r.interactive.body = r.text
    r.log_event = "new_order_started"
    return r


async def next_prompt_for(booking: Booking, available_slots) -> BookingReply:
    """Re-issue the prompt for the draft's current step, derived from which fields
    are already filled. Used to resume a draft after the continue/start-new choice
    without needing to stash the pre-interruption state."""
    if not booking.service_id:
        return _service_prompt()
    if not booking.line_items:
        return _resume_item_collection(booking)
    if not booking.customer_name:
        return _name_prompt(booking)
    if not booking.pickup_date:
        return _date_prompt(booking.service_name_snapshot or "your service")
    if not booking.pickup_slot_id:
        slots = await available_slots(booking.pickup_date, booking.pickup_area, booking.service_id)
        return _slot_prompt(slots, _format_date(booking.pickup_date))
    if not booking.pickup_address:
        return _address_prompt()
    if not booking.pickup_instruction_code:
        return _instructions_prompt()
    return _confirmation_prompt(booking)


# --- Customer name collection -----------------------------------------------
def _offered_name(booking: Booking) -> str | None:
    """A name we can offer the customer to confirm: a previously verified name,
    else the (unverified) WhatsApp profile name. Never used without confirmation."""
    return validate_name(booking.verified_name) or validate_name(booking.whatsapp_profile_name)


def _name_prompt(booking: Booking) -> BookingReply:
    """Ask for the booking name. A previously VERIFIED name is offered for reuse;
    otherwise the unverified WhatsApp profile name is offered for confirmation;
    otherwise we ask outright. The profile name is NEVER saved automatically."""
    verified = validate_name(booking.verified_name)
    if verified:
        body = f"Welcome back! Would you like to use the name {verified} for this booking?"
        return BookingReply(
            text=body, state=WAITING_FOR_NAME_CONFIRM,
            interactive=Interactive(kind="buttons", body=body, options=[
                Option(id="name_use", title="Use same name"),
                Option(id="name_change", title="Change name")]),
            log_event="name_confirm_verified")
    profile = validate_name(booking.whatsapp_profile_name)
    if profile:
        body = f"May I confirm your name for the booking? Is it {profile}?"
        return BookingReply(
            text=body, state=WAITING_FOR_NAME_CONFIRM,
            interactive=Interactive(kind="buttons", body=body, options=[
                Option(id="name_use", title="Yes, use this name"),
                Option(id="name_change", title="Enter another name")]),
            log_event="name_confirm_profile")
    return BookingReply(
        text="May I have your name for the booking?", state=WAITING_FOR_NAME,
        log_event="name_requested")


async def _finish_name(booking: Booking, name: str, available_slots) -> BookingReply:
    """Save the confirmed name (PATCH) and move to the next missing field."""
    updated = _with(booking, customer_name=name)
    reply = await next_prompt_for(updated, available_slots)
    reply.updates = {**reply.updates, "customer_name": name}
    reply.log_event = "customer_name_saved"
    return reply


async def _on_name(booking: Booking, inbound: Inbound, available_slots) -> BookingReply:
    name = validate_name(extract_name(inbound.text) or inbound.text)
    if not name:
        return BookingReply(
            text="Sorry, I didn't catch a valid name. Please type the name for the "
                 "booking (for example Sara or Amaan Patel).",
            state=WAITING_FOR_NAME, log_event="name_invalid")
    return await _finish_name(booking, name, available_slots)


async def _on_name_confirm(booking: Booking, inbound: Inbound, available_slots) -> BookingReply:
    sel = inbound.selection_id or ""
    text = (inbound.text or "").strip()
    low = text.lower()
    if sel == "name_use" or low in ("yes", "1", "use", "use same name", "confirm", "correct"):
        name = _offered_name(booking)
        if name:
            return await _finish_name(booking, name, available_slots)
        return BookingReply(text="May I have your name for the booking?",
                            state=WAITING_FOR_NAME)
    if sel == "name_change" or low in ("change", "2", "no", "another", "different",
                                       "change name", "enter another name"):
        return BookingReply(text="Sure — please type the name for the booking.",
                            state=WAITING_FOR_NAME, log_event="name_change_requested")
    # Anything else at this step is treated as the name itself.
    name = validate_name(extract_name(text) or text)
    if name:
        return await _finish_name(booking, name, available_slots)
    return _name_prompt(booking)


# --- Post-confirmation next actions + active-draft protection ----------------
_POST_ORDER_ACTIONS = [
    (NEW_ORDER, "Place another order"),
    (CHECK_ORDER_STATUS, "Check order status"),
    (HUMAN_SUPPORT, "Talk to support"),
]


def post_order_actions() -> BookingReply:
    """Shown right after an order is confirmed: what would you like to do next?"""
    return BookingReply(
        text="What would you like to do next?",
        state=POST_ORDER,
        interactive=Interactive(
            kind="list", body="What would you like to do next?",
            button_text="Choose", section_title="Next steps",
            options=[Option(id=a, title=t) for a, t in _POST_ORDER_ACTIONS],
        ),
        log_event="post_order_actions_shown",
    )


def resolve_post_order_action(inbound: Inbound, *, numbered: bool = False) -> str | None:
    """Map an inbound to a post-order action id. ``numbered`` allows the 1/2/3
    numbered-fallback mapping (only enabled when we know we're in the post-order
    context, so a bare '1' elsewhere is never misread as 'place another order')."""
    sel = inbound.selection_id or ""
    ids = {a for a, _ in _POST_ORDER_ACTIONS}
    if sel in ids:
        return sel
    text = (inbound.text or "").strip().lower()
    if numbered and text in {"1": NEW_ORDER, "2": CHECK_ORDER_STATUS, "3": HUMAN_SUPPORT}:
        return {"1": NEW_ORDER, "2": CHECK_ORDER_STATUS, "3": HUMAN_SUPPORT}[text]
    if is_new_order_intent(text):
        return NEW_ORDER
    if is_status_intent(text):
        return CHECK_ORDER_STATUS
    if any(w in text for w in ("talk to support", "human", "agent", "speak to")):
        return HUMAN_SUPPORT
    return None


def resume_or_new_prompt() -> BookingReply:
    return BookingReply(
        text="You already have an unfinished order. Would you like to continue it "
             "or start a new one?",
        state=RESUME_OR_NEW,
        interactive=Interactive(
            kind="buttons",
            body="You already have an unfinished order. Continue it or start a new one?",
            options=[
                Option(id="resume_continue", title="Continue current order"),
                Option(id="resume_new", title="Start a new order"),
                Option(id="resume_cancel", title="Cancel current order"),
            ],
        ),
        log_event="resume_or_new_asked",
    )


async def _on_resume_or_new(booking: Booking, inbound: Inbound, available_slots) -> BookingReply:
    sel = inbound.selection_id or ""
    text = (inbound.text or "").strip().lower()
    if sel == "resume_continue" or text in ("continue", "1", "keep", "current"):
        # restore the draft to its current step (state derived from filled fields)
        return await next_prompt_for(booking, available_slots)
    if sel == "resume_new" or text in ("new", "start new", "2", "start a new order"):
        return BookingReply(
            text="Sure — let's start a new order.", state=WAITING_FOR_SERVICE,
            start_new_order=True, log_event="resume_start_new")
    if sel == "resume_cancel" or text in ("cancel", "3"):
        return BookingReply(
            text="No problem — I've cancelled that order.", state=BOOKING_CANCELLED,
            cancel_now=True, log_event="booking_cancelled")
    return resume_or_new_prompt()


async def advance(booking: Booking, inbound: Inbound, *, today: _dt.date, available_slots) -> BookingReply:
    """Advance the booking one step. ``available_slots(pickup_date, emirate,
    service_id)`` is an ASYNC callable returning
    ``list[{slot_id,label,start_time,end_time}]`` (injected so the flow stays
    testable). Never mutates ``booking``; returns the updates to persist."""
    state = booking.conversation_state or WAITING_FOR_SERVICE

    # A cancel at any active step ends the booking (no operational order).
    if _CANCEL_WORDS.search(inbound.text or "") or inbound.selection_id == "cancel_booking":
        return BookingReply(
            text="No problem — I've cancelled this booking request. Message us any "
                 "time to start a new one.",
            state=BOOKING_CANCELLED,
            cancel_now=True,
            log_event="booking_cancelled",
        )

    # Opportunistic name capture: an explicit self-introduction ("I'm Ahmed",
    # "book it under Sara") is picked up at ANY step except the name steps
    # themselves (which parse the whole message as the name). The captured name is
    # merged into whatever the current step persists — never a full-object replace.
    name_updates: dict = {}
    if (not booking.customer_name
            and state not in (WAITING_FOR_NAME, WAITING_FOR_NAME_CONFIRM, EDITING_NAME)):
        nm = extract_name(inbound.text)
        if nm:
            booking = _with(booking, customer_name=nm)
            name_updates = {"customer_name": nm}

    reply = await _dispatch(state, booking, inbound, today, available_slots)
    if name_updates:
        reply.updates = {**name_updates, **reply.updates}
    return reply


async def _dispatch(state, booking, inbound, today, available_slots) -> BookingReply:
    if state == WAITING_FOR_SERVICE:
        return _on_service(booking, inbound)
    if state == WAITING_FOR_SUBCATEGORY:
        return _on_subcategory(booking, inbound)
    if state == WAITING_FOR_ITEM:
        return _on_item(booking, inbound)
    if state == WAITING_FOR_ITEM_QUANTITY:
        return _on_item_quantity(booking, inbound)
    if state == WAITING_FOR_MEASURE:
        return _on_measure(booking, inbound)
    if state == WAITING_FOR_MORE_ITEMS:
        return await _on_more_items(booking, inbound, available_slots)
    if state == WAITING_FOR_NAME:
        return await _on_name(booking, inbound, available_slots)
    if state == WAITING_FOR_NAME_CONFIRM:
        return await _on_name_confirm(booking, inbound, available_slots)
    if state == WAITING_FOR_PICKUP_DATE:
        return await _on_date(booking, inbound, today, available_slots)
    if state == WAITING_FOR_PICKUP_SLOT:
        return await _on_slot(booking, inbound, available_slots)
    if state == WAITING_FOR_ADDRESS:
        return _on_address(inbound)
    if state == WAITING_FOR_PICKUP_INSTRUCTIONS:
        return _on_instructions(booking, inbound)
    if state == WAITING_FOR_INSTRUCTION_TEXT:
        return _on_instruction_text(booking, inbound)
    if state == WAITING_FOR_CONFIRMATION:
        return _on_confirmation(booking, inbound)
    if state == WAITING_FOR_CHANGE_FIELD:
        return await _on_change_field(booking, inbound, available_slots)
    if state == RESUME_OR_NEW:
        return await _on_resume_or_new(booking, inbound, available_slots)
    # --- Targeted single-field edit (spec §"explicit edit state") -----------
    if state == EDITING_NAME:
        return _on_edit_name(booking, inbound)
    if state == EDITING_SERVICE:
        return await _on_edit_service(booking, inbound, available_slots)
    if state == EDITING_DATE:
        return await _on_edit_date(booking, inbound, today, available_slots)
    if state == EDITING_SLOT:
        return await _on_edit_slot(booking, inbound, available_slots)
    if state == EDITING_ADDRESS:
        return _on_edit_address(booking, inbound)
    if state == EDITING_INSTRUCTIONS:
        return _on_edit_instructions(booking, inbound)
    if state == EDITING_INSTRUCTION_TEXT:
        return _on_edit_instruction_text(booking, inbound)
    # Unknown/terminal — restart cleanly at service selection.
    return _service_prompt()


# --- Per-state handlers -----------------------------------------------------
def _on_service(booking: Booking, inbound: Inbound) -> BookingReply:
    category_code, reason = resolve_service(inbound)
    if reason == "ambiguous":
        # The single most common ambiguity — "ironing"/"pressing" — gets a focused
        # Clean & Press vs Press Only prompt (task spec §7/§20).
        if catalogue.is_ambiguous_iron(inbound.text):
            return _iron_disambiguation_prompt()
        r = _service_prompt()
        r.text = ("More than one service matches that — please pick the exact one "
                  "from the list below.")
        r.interactive.body = r.text
        r.log_event = "service_selection_ambiguous"
        return r
    if reason != "ok" or not category_code:
        r = _service_prompt()
        r.text = "Sorry, I didn't catch a valid service. Please choose one below:"
        r.interactive.body = r.text
        r.log_event = "service_selection_invalid"
        return r
    # Category picked -> collect the item(s) before name/date (task spec §6-8).
    return _enter_category(booking, category_code)


async def _on_date(booking: Booking, inbound: Inbound, today, available_slots) -> BookingReply:
    d, reason = parse_pickup_date(inbound, today)
    if reason == "other":
        return BookingReply(
            text="Sure — please type the pickup date you'd like (e.g. 25/07 or 25 July).",
            state=WAITING_FOR_PICKUP_DATE,
        )
    if reason == "past":
        return BookingReply(
            text="That date is in the past. Please choose today, tomorrow, or a future date.",
            state=WAITING_FOR_PICKUP_DATE,
            log_event="date_invalid_past",
        )
    if reason != "ok" or not d:
        return BookingReply(
            text="I couldn't read that date. Please type it as 25/07 or 25 July, or "
                 "reply Today / Tomorrow.",
            state=WAITING_FOR_PICKUP_DATE,
            log_event="date_invalid",
        )
    slots = await available_slots(d, booking.pickup_area, booking.service_id)
    reply = _slot_prompt(slots, _format_date(d))
    reply.updates = {"pickup_date": d}
    if reply.state == WAITING_FOR_PICKUP_SLOT:
        reply.log_event = "date_selected"
    return reply


async def _on_slot(booking: Booking, inbound: Inbound, available_slots) -> BookingReply:
    slots = await available_slots(booking.pickup_date, booking.pickup_area, booking.service_id)
    slot, reason = resolve_slot(inbound, slots)
    if reason != "ok" or not slot:
        r = _slot_prompt(slots, _format_date(booking.pickup_date))
        if r.state == WAITING_FOR_PICKUP_SLOT:
            r.text = "Please pick one of the available pickup times below:"
            if r.interactive:
                r.interactive.body = r.text
            r.log_event = "slot_selection_invalid"
        return r
    start = _dt.datetime.combine(booking.pickup_date, slot["start_time"], tzinfo=_GST)
    end = _dt.datetime.combine(booking.pickup_date, slot["end_time"], tzinfo=_GST)
    reply = _address_prompt()
    reply.updates = {
        "pickup_slot_id": slot["slot_id"],
        "pickup_slot": slot["label"],          # existing text column = display label
        "pickup_start_time": start,
        "pickup_end_time": end,
    }
    reply.log_event = "slot_selected"
    return reply


def _on_address(inbound: Inbound) -> BookingReply:
    if inbound.is_location:
        reply = _instructions_prompt()
        reply.updates = {
            "pickup_latitude": inbound.latitude,
            "pickup_longitude": inbound.longitude,
            "pickup_address": (inbound.text or "").strip() or "Shared WhatsApp location",
            "address_source": "whatsapp_location",
        }
        reply.log_event = "address_saved"
        return reply
    text = (inbound.text or "").strip()
    if len(text) < 5:
        return BookingReply(
            text="Please share a bit more detail for your pickup address, or send your "
                 "WhatsApp location.",
            state=WAITING_FOR_ADDRESS,
            log_event="address_invalid",
        )
    area = tools.extract_area(text)          # only if explicitly present — never inferred
    emirate = area_to_city(area) if area else None
    reply = _instructions_prompt()
    reply.updates = {
        "pickup_address": text,
        "pickup_area": area,
        "area": area,
        "pickup_emirate": emirate,
        "address_source": "typed",
    }
    reply.log_event = "address_saved"
    return reply


def _on_instructions(booking: Booking, inbound: Inbound) -> BookingReply:
    instr, reason = resolve_instruction(inbound)
    if reason != "ok" or not instr:
        r = _instructions_prompt()
        r.text = "Please choose one of the instruction options below:"
        if r.interactive:
            r.interactive.body = r.text
        r.log_event = "instruction_invalid"
        return r
    if instr["code"] == "other":
        return BookingReply(
            text="Sure — please type your pickup instructions for the driver.",
            state=WAITING_FOR_INSTRUCTION_TEXT,
        )
    text_val = None if instr["code"] == "none" else instr["label"]
    updated = _with(booking, pickup_instruction_code=instr["code"], pickup_instruction_text=text_val)
    reply = _confirmation_prompt(updated)
    reply.updates = {
        "pickup_instruction_code": instr["code"],
        "pickup_instruction_text": text_val,
    }
    reply.log_event = "instructions_saved"
    return reply


def _on_instruction_text(booking: Booking, inbound: Inbound) -> BookingReply:
    text = (inbound.text or "").strip()
    if not text:
        return BookingReply(
            text="Please type your pickup instructions, or reply 'none' if there are none.",
            state=WAITING_FOR_INSTRUCTION_TEXT,
        )
    updated = _with(booking, pickup_instruction_code="other", pickup_instruction_text=text)
    reply = _confirmation_prompt(updated)
    reply.updates = {"pickup_instruction_code": "other", "pickup_instruction_text": text}
    reply.log_event = "instructions_saved"
    return reply


def _on_confirmation(booking, inbound) -> BookingReply:
    sel = inbound.selection_id or ""
    text = (inbound.text or "").strip().lower()
    if sel == "confirm_booking" or text in ("confirm", "confirm booking", "yes", "book it", "1"):
        return BookingReply(
            text="",   # the webhook composes the final confirmation (with order id)
            state=BOOKING_CONFIRMED,
            confirm_now=True,
            log_event="booking_confirmed",
        )
    if sel == "change_details" or text in ("change", "change details", "edit", "2"):
        return _change_menu()
    if text in ("cancel", "3"):
        return BookingReply(
            text="No problem — I've cancelled this booking request. Message us any "
                 "time to start a new one.",
            state=BOOKING_CANCELLED,
            cancel_now=True,
            log_event="booking_cancelled",
        )
    # anything else -> re-show the summary
    return _confirmation_prompt(booking)


async def _on_change_field(booking, inbound, available_slots) -> BookingReply:
    """ORDER_EDIT_SELECTION: the customer picked ONE field to change. Route to the
    matching targeted-edit prompt (an EDITING_* state) that asks ONLY for that
    field. It does NOT re-enter linear collection, so nothing else is re-asked."""
    sel = inbound.selection_id or ""
    field_name = sel.split(":", 1)[1] if sel.startswith("change:") else (inbound.text or "").strip().lower()
    # numbered-fallback mapping (same order as _change_menu options)
    _NUMBERED = {"1": "name", "2": "service", "3": "date", "4": "slot",
                 "5": "address", "6": "instructions"}
    field_name = _NUMBERED.get(field_name, field_name)
    if field_name in ("name", "customer name"):
        return _edit_name_prompt()
    if field_name in ("service",):
        return _edit_service_prompt()
    if field_name in ("date", "pickup date"):
        return _edit_date_prompt()
    if field_name in ("slot", "pickup time", "time"):
        slots = await available_slots(booking.pickup_date, booking.pickup_area, booking.service_id)
        return _edit_slot_prompt(slots, _format_date(booking.pickup_date))
    if field_name in ("address",):
        return _edit_address_prompt()
    if field_name in ("instructions", "pickup instructions"):
        return _edit_instructions_prompt()
    # No/unrecognized field -> re-show the change menu (spec test 16).
    return _change_menu()


# --- Targeted single-field edit: prompts (ask ONLY the chosen field) --------
def _edit_name_prompt() -> BookingReply:
    return BookingReply(
        text="What name should we use for this order?",
        state=EDITING_NAME,
        log_event="edit_field_name",
    )


def _edit_service_prompt() -> BookingReply:
    return BookingReply(
        text="Which service would you like instead?",
        state=EDITING_SERVICE,
        interactive=Interactive(
            kind="list", body="Which service would you like instead?",
            button_text="Choose a service", section_title="Our services",
            options=_service_options(),
        ),
        log_event="edit_field_service",
    )


def _edit_date_prompt() -> BookingReply:
    return BookingReply(
        text="What pickup date would you prefer?",
        state=EDITING_DATE,
        interactive=Interactive(
            kind="buttons", body="What pickup date would you prefer?",
            options=[
                Option(id="date:today", title="Today"),
                Option(id="date:tomorrow", title="Tomorrow"),
                Option(id="date:other", title="Choose another date"),
            ],
        ),
        log_event="edit_field_date",
    )


def _edit_slot_prompt(slots: list[dict], date_label: str, *, note: str | None = None) -> BookingReply:
    if not slots:
        return BookingReply(
            text=(f"Sorry, we have no pickup slots for {date_label}. "
                  "Please choose another day."),
            state=EDITING_DATE,
            interactive=Interactive(
                kind="buttons", body=f"No slots for {date_label}. Pick another day?",
                options=[
                    Option(id="date:today", title="Today"),
                    Option(id="date:tomorrow", title="Tomorrow"),
                    Option(id="date:other", title="Choose another date"),
                ],
            ),
            log_event="edit_no_slots_available",
        )
    body = note or "What pickup time would you prefer?"
    return BookingReply(
        text=body,
        state=EDITING_SLOT,
        interactive=Interactive(
            kind="list", body=body, button_text="Choose a time",
            section_title="Available pickup times", options=_slot_options(slots),
        ),
        log_event="edit_field_slot",
    )


def _edit_address_prompt() -> BookingReply:
    return BookingReply(
        text="What is the new pickup address? You can also share your WhatsApp location.",
        state=EDITING_ADDRESS,
        log_event="edit_field_address",
    )


def _edit_instructions_prompt() -> BookingReply:
    return BookingReply(
        text="What pickup instructions would you like instead?",
        state=EDITING_INSTRUCTIONS,
        interactive=Interactive(
            kind="list", body="What pickup instructions would you like instead?",
            button_text="Choose", section_title="Pickup instructions",
            options=_instruction_options(),
        ),
        log_event="edit_field_instructions",
    )


def _back_to_review(updated: Booking, updates: dict, *, log: str) -> BookingReply:
    """Return straight to the order summary after a successful edit, carrying a
    PATCH of ONLY the changed columns. Staying at WAITING_FOR_CONFIRMATION means
    the edit is not confirmed until the customer re-confirms the revised summary
    (spec: customer_confirmed reset)."""
    reply = _confirmation_prompt(updated, header="Here are your updated pickup details:")
    reply.updates = updates
    reply.log_event = log
    return reply


# --- Targeted single-field edit: value handlers -----------------------------
# Each updates ONLY its field (PATCH), preserves everything else, and returns to
# the summary. Invalid input keeps the customer in the SAME edit state.
def _on_edit_name(booking, inbound) -> BookingReply:
    name = validate_name(extract_name(inbound.text) or inbound.text)
    if not name:
        return BookingReply(
            text="Please type a valid name for the order (for example Sara or "
                 "Amaan Patel).",
            state=EDITING_NAME, log_event="edit_name_invalid")
    updated = _with(booking, customer_name=name)
    return _back_to_review(updated, {"customer_name": name}, log="edit_name_saved")


async def _on_edit_service(booking, inbound, available_slots) -> BookingReply:
    service_id, reason = resolve_service(inbound)
    if reason == "ambiguous":
        r = _edit_service_prompt()
        r.text = "More than one service matches that — please pick the exact one below."
        r.interactive.body = r.text
        r.log_event = "edit_service_ambiguous"
        return r
    if reason != "ok" or not service_id:
        r = _edit_service_prompt()
        r.text = "Sorry, I didn't catch a valid service. Please choose one below:"
        r.interactive.body = r.text
        r.log_event = "edit_service_invalid"
        return r
    category_code = service_id
    # Same category chosen — nothing changes, return to the summary.
    if category_code == booking.service_id:
        return _confirmation_prompt(booking, header="Here are your updated pickup details:")
    # A different category invalidates the collected items (they belong to the old
    # category), so we clear them and re-collect for the new category. This is an
    # item-only re-collection, NOT a full restart: name/date/slot/address are all
    # preserved and the flow returns straight to the summary once items are chosen
    # (task spec §16 — a targeted edit never re-asks the address etc.).
    cleared = _with(booking, service_id=category_code, line_items=None,
                    browse_service_code=None, pending_item_code=None)
    reply = _enter_category(cleared, category_code)
    reply.updates = {
        **(reply.updates or {}),
        "line_items": None, "browse_service_code": reply.updates.get("browse_service_code"),
        "pending_item_code": None, "subtotal_amount": None, "vat_amount": None,
        "estimated_total": None, "amount": None, "pricing_is_estimated": None,
    }
    reply.log_event = "edit_service_reset_items"
    return reply


async def _on_edit_date(booking, inbound, today, available_slots) -> BookingReply:
    d, reason = parse_pickup_date(inbound, today)
    if reason == "other":
        return BookingReply(
            text="Sure — please type the pickup date you'd like (e.g. 25/07 or 25 July).",
            state=EDITING_DATE)
    if reason == "past":
        return BookingReply(
            text="That date is in the past. Please choose today, tomorrow, or a future date.",
            state=EDITING_DATE, log_event="edit_date_invalid_past")
    if reason != "ok" or not d:
        return BookingReply(
            text="I couldn't read that date. Please type it as 25/07 or 25 July, or reply "
                 "Today / Tomorrow.",
            state=EDITING_DATE, log_event="edit_date_invalid")
    slots = await available_slots(d, booking.pickup_area, booking.service_id)
    by_id = {s["slot_id"]: s for s in slots}
    if booking.pickup_slot_id and booking.pickup_slot_id in by_id:
        # Existing slot still available on the new date — keep it, recompute the
        # concrete start/end datetimes for the new date, return to review.
        s = by_id[booking.pickup_slot_id]
        start = _dt.datetime.combine(d, s["start_time"], tzinfo=_GST)
        end = _dt.datetime.combine(d, s["end_time"], tzinfo=_GST)
        updated = _with(booking, pickup_date=d)
        return _back_to_review(
            updated,
            {"pickup_date": d, "pickup_start_time": start, "pickup_end_time": end},
            log="edit_date_saved")
    # Slot not available on the new date — save the date, clear the slot, and ask
    # ONLY for a replacement slot (spec: explain + ask only for a new slot).
    updated = _with(booking, pickup_date=d, pickup_slot_id=None, pickup_slot_label=None)
    prompt = _edit_slot_prompt(
        slots, _format_date(d),
        note=f"Your previous pickup time isn't available on {_format_date(d)}. "
             "Please choose a new time:")
    prompt.updates = {"pickup_date": d, "pickup_slot_id": None, "pickup_slot": None,
                      "pickup_start_time": None, "pickup_end_time": None}
    prompt.log_event = "edit_date_slot_revalidate"
    return prompt


async def _on_edit_slot(booking, inbound, available_slots) -> BookingReply:
    slots = await available_slots(booking.pickup_date, booking.pickup_area, booking.service_id)
    slot, reason = resolve_slot(inbound, slots)
    if reason != "ok" or not slot:
        r = _edit_slot_prompt(slots, _format_date(booking.pickup_date))
        if r.state == EDITING_SLOT:
            r.text = "Please choose one of the available pickup times below:"
            if r.interactive:
                r.interactive.body = r.text
            r.log_event = "edit_slot_invalid"
        return r
    start = _dt.datetime.combine(booking.pickup_date, slot["start_time"], tzinfo=_GST)
    end = _dt.datetime.combine(booking.pickup_date, slot["end_time"], tzinfo=_GST)
    updated = _with(booking, pickup_slot_id=slot["slot_id"], pickup_slot_label=slot["label"])
    return _back_to_review(
        updated,
        {"pickup_slot_id": slot["slot_id"], "pickup_slot": slot["label"],
         "pickup_start_time": start, "pickup_end_time": end},
        log="edit_slot_saved")


def _on_edit_address(booking, inbound) -> BookingReply:
    if inbound.is_location:
        addr = (inbound.text or "").strip() or "Shared WhatsApp location"
        updated = _with(booking, pickup_address=addr)
        return _back_to_review(
            updated,
            {"pickup_latitude": inbound.latitude, "pickup_longitude": inbound.longitude,
             "pickup_address": addr, "address_source": "whatsapp_location"},
            log="edit_address_saved")
    text = (inbound.text or "").strip()
    if len(text) < 5:
        return BookingReply(
            text="Please share a bit more detail for your pickup address, or send your "
                 "WhatsApp location.",
            state=EDITING_ADDRESS, log_event="edit_address_invalid")
    area = tools.extract_area(text)
    emirate = area_to_city(area) if area else None
    updated = _with(booking, pickup_address=text, pickup_area=area)
    return _back_to_review(
        updated,
        {"pickup_address": text, "pickup_area": area, "area": area,
         "pickup_emirate": emirate, "address_source": "typed"},
        log="edit_address_saved")


def _on_edit_instructions(booking, inbound) -> BookingReply:
    instr, reason = resolve_instruction(inbound)
    if reason != "ok" or not instr:
        r = _edit_instructions_prompt()
        r.text = "Please choose one of the instruction options below:"
        if r.interactive:
            r.interactive.body = r.text
        r.log_event = "edit_instruction_invalid"
        return r
    if instr["code"] == "other":
        return BookingReply(
            text="Sure — please type your pickup instructions for the driver.",
            state=EDITING_INSTRUCTION_TEXT)
    text_val = None if instr["code"] == "none" else instr["label"]
    updated = _with(booking, pickup_instruction_code=instr["code"], pickup_instruction_text=text_val)
    return _back_to_review(
        updated,
        {"pickup_instruction_code": instr["code"], "pickup_instruction_text": text_val},
        log="edit_instructions_saved")


def _on_edit_instruction_text(booking, inbound) -> BookingReply:
    text = (inbound.text or "").strip()
    if not text:
        return BookingReply(
            text="Please type your pickup instructions, or reply 'none' if there are none.",
            state=EDITING_INSTRUCTION_TEXT)
    updated = _with(booking, pickup_instruction_code="other", pickup_instruction_text=text)
    return _back_to_review(
        updated,
        {"pickup_instruction_code": "other", "pickup_instruction_text": text},
        log="edit_instructions_saved")


def _with(b: Booking, **changes) -> Booking:
    data = dict(b.__dict__)
    data.update(changes)
    return Booking(**data)


def numbered_fallback(interactive: Interactive) -> str:
    """Plain numbered-text version of an interactive list/buttons, used when the
    Evolution interactive send fails or is unsupported. A numeric reply ("2") is
    resolved by the FSM against the SAME (deterministically ordered) options, so
    the fallback still maps back to a real service/slot/instruction id."""
    lines = [interactive.body, ""]
    for i, opt in enumerate(interactive.options, 1):
        lines.append(f"{i}. {opt.title}")
    lines.append("")
    lines.append("Reply with the number of your choice.")
    return "\n".join(lines)
