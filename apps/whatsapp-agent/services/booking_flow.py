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
from rules import active_service_catalog, pickup_instructions, service_by_id
from services.order_extraction import area_to_city

# --- States -----------------------------------------------------------------
WAITING_FOR_SERVICE = "waiting_for_service"
WAITING_FOR_PICKUP_DATE = "waiting_for_pickup_date"
WAITING_FOR_PICKUP_SLOT = "waiting_for_pickup_slot"
WAITING_FOR_ADDRESS = "waiting_for_address"
WAITING_FOR_PICKUP_INSTRUCTIONS = "waiting_for_pickup_instructions"
WAITING_FOR_INSTRUCTION_TEXT = "waiting_for_instruction_text"
WAITING_FOR_CONFIRMATION = "waiting_for_confirmation"
WAITING_FOR_CHANGE_FIELD = "waiting_for_change_field"
BOOKING_CONFIRMED = "booking_confirmed"
BOOKING_CANCELLED = "booking_cancelled"

ACTIVE_STATES = frozenset({
    WAITING_FOR_SERVICE, WAITING_FOR_PICKUP_DATE, WAITING_FOR_PICKUP_SLOT,
    WAITING_FOR_ADDRESS, WAITING_FOR_PICKUP_INSTRUCTIONS, WAITING_FOR_INSTRUCTION_TEXT,
    WAITING_FOR_CONFIRMATION, WAITING_FOR_CHANGE_FIELD,
})
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
    log_event: str | None = None  # structured-log hint for the webhook


@dataclass
class Booking:
    """The subset of the open draft-order row the FSM reasons over."""
    conversation_state: str | None = None
    service_id: str | None = None
    service_name_snapshot: str | None = None
    pickup_date: _dt.date | None = None
    pickup_slot_id: str | None = None
    pickup_slot_label: str | None = None
    pickup_address: str | None = None
    pickup_area: str | None = None
    pickup_instruction_code: str | None = None
    pickup_instruction_text: str | None = None


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


def is_book_pickup_intent(text: str) -> bool:
    """True when a free-text message expresses intent to book a pickup. Used only
    to START a booking — it never selects a service (that is a separate step)."""
    return bool(_BOOK_INTENT.search(text or ""))


# --- Service catalogue helpers ----------------------------------------------
def _service_options() -> list[Option]:
    opts: list[Option] = []
    for s in active_service_catalog():
        desc = (s.get("description") or "").strip()
        opts.append(Option(
            id=f"service:{s.get('service_id', s.get('key'))}",
            title=s.get("display_name") or s.get("label"),
            description=(desc[:69] + "…") if len(desc) > 70 else (desc or None),
        ))
    return opts


def resolve_service(inbound: Inbound) -> tuple[str | None, str]:
    """Return (service_id, reason). reason: 'ok' | 'ambiguous' | 'invalid'."""
    services = active_service_catalog()
    ids = {s.get("service_id", s.get("key")) for s in services}

    sel = inbound.selection_id or ""
    if sel.startswith("service:"):
        key = sel.split(":", 1)[1]
        return (key, "ok") if key in ids else (None, "invalid")

    text = (inbound.text or "").strip()
    # numbered fallback ("2")
    if text.isdigit():
        idx = int(text) - 1
        opts = _service_options()
        if 0 <= idx < len(opts):
            return (opts[idx].id.split(":", 1)[1], "ok")
        return (None, "invalid")

    # free text -> match against catalogue aliases; resolve only on a UNIQUE hit
    lowered = text.lower()
    matched: set[str] = set()
    for s in services:
        sid = s.get("service_id", s.get("key"))
        for alias in (s.get("aliases") or s.get("keywords") or []):
            if alias and alias.lower() in lowered:
                matched.add(sid)
                break
    if len(matched) == 1:
        return (matched.pop(), "ok")
    if len(matched) > 1:
        return (None, "ambiguous")
    return (None, "invalid")


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


def _summary_text(b: Booking) -> str:
    instr = b.pickup_instruction_text or "No additional instructions"
    return (
        "Please confirm your pickup details:\n\n"
        f"Service: {b.service_name_snapshot or '—'}\n"
        f"Pickup date: {_format_date(b.pickup_date)}\n"
        f"Pickup time: {b.pickup_slot_label or '—'}\n"
        f"Address: {b.pickup_address or '—'}\n"
        f"Instructions: {instr}"
    )


def _confirmation_prompt(b: Booking) -> BookingReply:
    return BookingReply(
        text=_summary_text(b),
        state=WAITING_FOR_CONFIRMATION,
        interactive=Interactive(
            kind="buttons",
            body=_summary_text(b),
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

    if state == WAITING_FOR_SERVICE:
        return _on_service(inbound)
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
    # Unknown/terminal — restart cleanly at service selection.
    return _service_prompt()


# --- Per-state handlers -----------------------------------------------------
def _on_service(inbound: Inbound) -> BookingReply:
    service_id, reason = resolve_service(inbound)
    if reason == "ambiguous":
        r = _service_prompt()
        r.text = ("More than one service matches that — please pick the exact one "
                  "from the list below.")
        r.interactive.body = r.text
        r.log_event = "service_selection_ambiguous"
        return r
    if reason != "ok" or not service_id:
        r = _service_prompt()
        r.text = "Sorry, I didn't catch a valid service. Please choose one below:"
        r.interactive.body = r.text
        r.log_event = "service_selection_invalid"
        return r
    svc = service_by_id(service_id) or {}
    label = svc.get("display_name") or svc.get("label") or service_id
    reply = _date_prompt(label)
    reply.updates = {
        "service_id": service_id,
        "service": label,                       # back-compat label mirror
        "service_display_name": label,
        "service_name_snapshot": label,
        "unit_type": svc.get("unit_type"),
        "requires_manual_quote": bool(svc.get("requires_manual_quote")),
        "_touch_service_selected_at": True,     # webhook fills the timestamp
    }
    reply.log_event = "service_selected"
    return reply


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
    sel = inbound.selection_id or ""
    field_name = sel.split(":", 1)[1] if sel.startswith("change:") else (inbound.text or "").strip().lower()
    # numbered-fallback mapping (same order as _change_menu options)
    _NUMBERED = {"1": "service", "2": "date", "3": "slot", "4": "address", "5": "instructions"}
    field_name = _NUMBERED.get(field_name, field_name)
    if field_name in ("service",):
        return _service_prompt()
    if field_name in ("date", "pickup date"):
        # revalidate the slot after a date change: clear it so it is re-picked
        r = _date_prompt(booking.service_name_snapshot or "your service")
        r.updates = {"pickup_slot_id": None, "pickup_slot": None,
                     "pickup_start_time": None, "pickup_end_time": None}
        return r
    if field_name in ("slot", "pickup time", "time"):
        slots = await available_slots(booking.pickup_date, booking.pickup_area, booking.service_id)
        return _slot_prompt(slots, _format_date(booking.pickup_date))
    if field_name in ("address",):
        return _address_prompt()
    if field_name in ("instructions", "pickup instructions"):
        return _instructions_prompt()
    return _change_menu()


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
